import asyncio
import re
import urllib.parse
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext

from utils.logging import get_logger

logger = get_logger("search_scraper")


class TikTokSearchScraper:
    """Local TikTok Search & Discovery Scraper using Headless Chromium."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def search_videos(
        self,
        query: str,
        count: int = 10,
        scroll_limit: int = 3,
    ) -> Dict[str, Any]:
        """Search TikTok videos by keyword or phrase.

        Args:
            query: Keyword or phrase to search for.
            count: Desired number of video results (default: 10, max: 30).
            scroll_limit: Number of page scrolls to trigger pagination.
        """
        logger.info(f"Starting TikTok search discovery for query='{query}' (count={count})...")
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.tiktok.com/search?q={encoded_query}"

        results: List[Dict[str, Any]] = []
        seen_urls = set()

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
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                page = await context.new_page()

                # Step 1: Warm up session on explore page to establish anti-bot cookies
                logger.info("Warming up TikTok session on /explore...")
                try:
                    await page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"Session warmup notice: {e}")

                # Step 2: Navigate to search page
                logger.info(f"Navigating to search page: {search_url}")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3500)

                # Step 3: Scroll and extract video cards
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

                        # Extract video ID
                        match = re.search(r"/video/(\d+)", raw_url)
                        if not match:
                            continue
                        vid_id = match.group(1)

                        # Clean canonical URL
                        canonical_url = raw_url.split("?")[0]
                        seen_urls.add(raw_url)
                        seen_urls.add(canonical_url)

                        results.append({
                            "id": vid_id,
                            "url": canonical_url,
                            "author": c.get("author"),
                            "description": c.get("desc"),
                            "thumbnail_url": c.get("thumbnail"),
                        })

                        if len(results) >= count:
                            break

                    if len(results) >= count:
                        break

                    # Scroll down to trigger more search results
                    logger.info(f"Scrolling page ({scroll_idx + 1}/{scroll_limit})...")
                    await page.evaluate("window.scrollBy(0, 1500)")
                    await page.wait_for_timeout(2500)

                await browser.close()

            logger.info(f"Search discovery complete. Extracted {len(results)} videos.")
            return {
                "success": True,
                "platform": "tiktok",
                "query": query,
                "count": len(results),
                "videos": results[:count],
            }

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
