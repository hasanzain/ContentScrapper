import asyncio
import random
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright

from utils.logging import get_logger

logger = get_logger("search_scraper")

# Per-page navigation timeout. 3 fallback strategies × this = max wall-clock.
# Keep low so total stays well under Claude stream idle watchdog (300s).
PAGE_TIMEOUT_MS = 10_000  # 10s per page load

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

STEALTH_JS = """
// Anti-automation detection evasion
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = {
    runtime: {},
    app: {},
    csi: () => {},
    loadTimes: () => {},
};
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'id'] });
"""


class TikTokSearchScraper:
    """Resilient TikTok Search & Discovery Scraper with Anti-Block Fallbacks and Caching."""

    def __init__(self, headless: bool = True, cache_ttl: int = 900):
        self.headless = headless
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._last_request_time = 0.0

    async def _throttle(self, min_delay: float = 1.5):
        """Enforce adaptive pacing between successive browser launches."""
        elapsed = time.time() - self._last_request_time
        if elapsed < min_delay:
            wait_time = min_delay - elapsed + random.uniform(0.3, 0.8)
            await asyncio.sleep(wait_time)
        self._last_request_time = time.time()

    async def search_videos(
        self,
        query: str,
        count: int = 10,
        scroll_limit: int = 3,
    ) -> Dict[str, Any]:
        """Search TikTok videos by keyword or phrase with anti-blocking fallbacks.

        Args:
            query: Keyword or phrase to search for.
            count: Desired number of video results (default: 10, max: 30).
            scroll_limit: Number of page scrolls to trigger pagination.
        """
        cache_key = f"{query.strip().lower()}:{count}"
        if cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"Returning cached search results for '{query}' (ttl={int(self.cache_ttl - (time.time() - cached_time))}s left)")
                return cached_val

        await self._throttle()
        logger.info(f"Starting TikTok search discovery for query='{query}' (count={count})...")

        results: List[Dict[str, Any]] = []
        seen_urls = set()
        ua = random.choice(USER_AGENTS)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                await context.add_init_script(STEALTH_JS)
                page = await context.new_page()

                # Strategy 1: Direct Web Search
                encoded_query = urllib.parse.quote(query)
                search_url = f"https://www.tiktok.com/search?q={encoded_query}"
                logger.info(f"Strategy 1: Direct search -> {search_url}")

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    await page.wait_for_timeout(3000)

                    for scroll_idx in range(scroll_limit):
                        cards = await page.evaluate("""() => {
                            const items = [];
                            const links = document.querySelectorAll("a[href*='/video/']");
                            for (const a of links) {
                                const href = a.href;
                                let container = a.parentElement;
                                for (let k = 0; k < 6 && container && container.parentElement; k++) {
                                    if (container.querySelector("[data-e2e='search-card-user-unique-id']")) break;
                                    container = container.parentElement;
                                }
                                const card = container || a;
                                const authorEl = card.querySelector("[data-e2e='search-card-user-unique-id'], [data-e2e='search-card-user-link']");
                                const descEl = card.querySelector("[data-e2e='search-card-video-caption'], [data-e2e='search-card-desc']");
                                const statsEl = card.querySelector("[data-e2e='search-card-like-container']");
                                const imgEl = card.querySelector("img");

                                items.push({
                                    url: href,
                                    author: authorEl ? authorEl.textContent.trim() : null,
                                    desc: descEl ? descEl.textContent.trim() : null,
                                    stats: statsEl ? statsEl.textContent.trim() : null,
                                    thumbnail: imgEl ? imgEl.src : null,
                                });
                            }
                            return items;
                        }""")

                        for c in cards:
                            raw_url = c.get("url")
                            if not raw_url or raw_url in seen_urls:
                                continue
                            m = re.search(r"/video/(\d+)", raw_url)
                            if not m:
                                continue
                            vid_id = m.group(1)
                            canonical_url = raw_url.split("?")[0]
                            seen_urls.add(raw_url)
                            seen_urls.add(canonical_url)

                            author = c.get("author")
                            if not author:
                                author_m = re.search(r"/@([^/]+)/", canonical_url)
                                if author_m:
                                    author = author_m.group(1)

                            results.append({
                                "id": vid_id,
                                "url": canonical_url,
                                "author": author,
                                "description": c.get("desc"),
                                "thumbnail_url": c.get("thumbnail"),
                            })
                            if len(results) >= count:
                                break

                        if len(results) >= count or len(cards) == 0:
                            break

                        await page.evaluate("window.scrollBy(0, 1500)")
                        await page.wait_for_timeout(2000)

                except Exception as exc:
                    logger.warning(f"Direct search encountered obstacle: {exc}")

                # Strategy 2: Hashtag Discovery Fallback (if direct search blocked or insufficient results)
                if len(results) < count:
                    keywords = [w.strip("#") for w in re.findall(r"\b\w+\b", query) if len(w) > 1]
                    keywords.sort(key=len, reverse=True)
                    logger.info(f"Strategy 2: Hashtag fallback with keywords: {keywords}")

                    for kw in keywords:
                        if len(results) >= count:
                            break
                        tag_url = f"https://www.tiktok.com/tag/{urllib.parse.quote(kw)}"
                        logger.info(f"Navigating to hashtag page: {tag_url}")

                        try:
                            await page.goto(tag_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                            await page.wait_for_timeout(2500)

                            tag_cards = await page.evaluate("""() => {
                                const items = [];
                                const links = document.querySelectorAll("a[href*='/video/']");
                                for (const a of links) {
                                    const href = a.href;
                                    let container = a.parentElement;
                                    for (let k = 0; k < 6 && container && container.parentElement; k++) {
                                        container = container.parentElement;
                                    }
                                    const card = container || a;
                                    const img = card.querySelector('img');
                                    const text = card.innerText || '';
                                    items.push({
                                        url: href,
                                        thumbnail: img ? img.src : null,
                                        desc: text.slice(0, 150)
                                    });
                                }
                                return items;
                            }""")

                            for c in tag_cards:
                                raw_url = c.get("url")
                                if not raw_url or raw_url in seen_urls:
                                    continue
                                m = re.search(r"/video/(\d+)", raw_url)
                                if not m:
                                    continue
                                vid_id = m.group(1)
                                canonical_url = raw_url.split("?")[0]
                                seen_urls.add(raw_url)
                                seen_urls.add(canonical_url)

                                author_m = re.search(r"/@([^/]+)/", canonical_url)
                                author = author_m.group(1) if author_m else None
                                desc = c.get("desc", "").replace("\n", " ").strip()

                                results.append({
                                    "id": vid_id,
                                    "url": canonical_url,
                                    "author": author,
                                    "description": desc or f"TikTok video #{kw}",
                                    "thumbnail_url": c.get("thumbnail"),
                                })
                                if len(results) >= count:
                                    break
                        except Exception as tag_exc:
                            logger.warning(f"Hashtag fallback #{kw} notice: {tag_exc}")

                # Strategy 3: Explore Trending Fallback (if still insufficient)
                if len(results) < count:
                    logger.info("Strategy 3: Explore trending feed fallback...")
                    try:
                        await page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                        await page.wait_for_timeout(2500)

                        explore_cards = await page.evaluate("""() => {
                            const items = [];
                            const links = document.querySelectorAll("a[href*='/video/']");
                            for (const a of links) {
                                const href = a.href;
                                let container = a.parentElement;
                                for (let k = 0; k < 6 && container && container.parentElement; k++) {
                                    container = container.parentElement;
                                }
                                const card = container || a;
                                const img = card.querySelector('img');
                                const text = card.innerText || '';
                                items.push({
                                    url: href,
                                    thumbnail: img ? img.src : null,
                                    desc: text.slice(0, 150)
                                });
                            }
                            return items;
                        }""")

                        for c in explore_cards:
                            raw_url = c.get("url")
                            if not raw_url or raw_url in seen_urls:
                                continue
                            m = re.search(r"/video/(\d+)", raw_url)
                            if not m:
                                continue
                            vid_id = m.group(1)
                            canonical_url = raw_url.split("?")[0]
                            seen_urls.add(raw_url)
                            seen_urls.add(canonical_url)

                            author_m = re.search(r"/@([^/]+)/", canonical_url)
                            author = author_m.group(1) if author_m else None
                            desc = c.get("desc", "").replace("\n", " ").strip()

                            results.append({
                                "id": vid_id,
                                "url": canonical_url,
                                "author": author,
                                "description": desc or "TikTok trending video",
                                "thumbnail_url": c.get("thumbnail"),
                            })
                            if len(results) >= count:
                                break
                    except Exception as exp_exc:
                        logger.warning(f"Explore fallback notice: {exp_exc}")

                await browser.close()

            response_data = {
                "success": len(results) > 0,
                "platform": "tiktok",
                "query": query,
                "count": len(results),
                "videos": results[:count],
            }
            if len(results) > 0:
                self._cache[cache_key] = (time.time(), response_data)

            logger.info(f"Search discovery complete. Extracted {len(results)} videos.")
            return response_data

        except Exception as e:
            logger.error(f"Search discovery failed for query '{query}': {e}", exc_info=True)
            return {
                "success": False,
                "platform": "tiktok",
                "query": query,
                "count": 0,
                "videos": [],
                "error": str(e),
            }
