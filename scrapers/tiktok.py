import random
import re
import time
import urllib.request
from typing import Any, Dict, List, Optional
import yt_dlp

from scrapers.base import BaseScraper
from utils.logging import get_logger, YtDlpStderrLogger

logger = get_logger("tiktok_scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


class TikTokScraper(BaseScraper):
    """Resilient TikTok scraper powered by yt-dlp with anti-blocking defenses, retry, and caching."""

    def __init__(self, cache_ttl: int = 900):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._last_request_time = 0.0

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": "https://www.tiktok.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _throttle(self, min_interval: float = 1.0):
        """Paces requests to avoid tripping TikTok IP burst rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            wait = min_interval - elapsed + random.uniform(0.2, 0.6)
            time.sleep(wait)
        self._last_request_time = time.time()

    def _get_ydl_opts(self) -> Dict[str, Any]:
        return {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "http_headers": self._get_headers(),
            "logger": YtDlpStderrLogger(),
            "extract_flat": False,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "sleep_interval": 1,
            "max_sleep_interval": 2,
        }

    def scrape_video(self, url: str) -> Dict[str, Any]:
        """Extract metadata for a TikTok video with caching and retry backoff."""
        clean_url = url.split("?")[0].strip()
        cache_key = f"video:{clean_url}"

        if cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"Returning cached video metadata for '{clean_url}'")
                return cached_val

        max_retries = 2
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                self._throttle()
                ydl_opts = self._get_ydl_opts()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        return {
                            "success": False,
                            "platform": "tiktok",
                            "url": url,
                            "error": "Failed to extract metadata: empty result",
                        }
                    res = self._normalize_video_data(url, info)
                    self._cache[cache_key] = (time.time(), res)
                    return res

            except Exception as exc:
                last_exc = exc
                logger.warning(f"Scrape video attempt {attempt + 1}/{max_retries + 1} failed for '{url}': {exc}")
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(sleep_time)

        logger.error(f"Error scraping TikTok video '{url}' after {max_retries + 1} attempts: {last_exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "url": url,
            "error": str(last_exc),
        }

    def get_transcript(self, url: str) -> Dict[str, Any]:
        """Extract transcript/captions for a TikTok video with caching and retry backoff."""
        clean_url = url.split("?")[0].strip()
        cache_key = f"transcript:{clean_url}"

        if cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.info(f"Returning cached transcript for '{clean_url}'")
                return cached_val

        max_retries = 2
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                self._throttle()
                ydl_opts = self._get_ydl_opts()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        return {
                            "success": False,
                            "platform": "tiktok",
                            "url": url,
                            "available": False,
                            "segments": [],
                            "text": "",
                            "error": "Failed to extract video info",
                        }

                    subtitles = info.get("subtitles") or {}
                    auto_subtitles = info.get("automatic_captions") or {}
                    all_subs = {**subtitles, **auto_subtitles}

                    if not all_subs:
                        res = {
                            "success": True,
                            "platform": "tiktok",
                            "url": url,
                            "available": False,
                            "language": None,
                            "segments": [],
                            "text": "",
                        }
                        self._cache[cache_key] = (time.time(), res)
                        return res

                    # Find first available subtitle track
                    chosen_lang = None
                    chosen_url = None
                    for lang, formats in all_subs.items():
                        for f in formats:
                            if f.get("url"):
                                chosen_lang = lang
                                chosen_url = f.get("url")
                                break
                        if chosen_url:
                            break

                    if not chosen_url:
                        res = {
                            "success": True,
                            "platform": "tiktok",
                            "url": url,
                            "available": False,
                            "language": None,
                            "segments": [],
                            "text": "",
                        }
                        self._cache[cache_key] = (time.time(), res)
                        return res

                    # Fetch and parse subtitle content
                    vtt_text = self._fetch_url_content(chosen_url)
                    segments, full_text = self._parse_vtt(vtt_text)

                    res = {
                        "success": True,
                        "platform": "tiktok",
                        "url": url,
                        "available": len(segments) > 0,
                        "language": chosen_lang,
                        "segments": segments,
                        "text": full_text,
                    }
                    self._cache[cache_key] = (time.time(), res)
                    return res

            except Exception as exc:
                last_exc = exc
                logger.warning(f"Get transcript attempt {attempt + 1}/{max_retries + 1} failed for '{url}': {exc}")
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(sleep_time)

        logger.error(f"Error getting transcript for '{url}': {last_exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "url": url,
            "available": False,
            "segments": [],
            "text": "",
            "error": str(last_exc),
        }

    def _fetch_url_content(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self._get_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse_time(time_str: str) -> float:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(parts[0])

    def _parse_vtt(self, vtt_content: str) -> tuple[List[Dict[str, Any]], str]:
        """Parse WEBVTT text into structured segments and full plain text."""
        segments: List[Dict[str, Any]] = []
        cue_re = re.compile(
            r"((?:\d{2}:)?\d{2}:\d{2}[\.,]\d{3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}[\.,]\d{3})"
        )

        lines = vtt_content.splitlines()
        i = 0
        current_texts: List[str] = []

        while i < len(lines):
            line = lines[i].strip()
            match = cue_re.search(line)
            if match:
                start_str, end_str = match.group(1), match.group(2)
                start_sec = round(self._parse_time(start_str.replace(",", ".")), 3)
                end_sec = round(self._parse_time(end_str.replace(",", ".")), 3)

                # Collect text lines until next blank line or cue
                text_lines: List[str] = []
                i += 1
                while i < len(lines):
                    sub_line = lines[i].strip()
                    if not sub_line:
                        break
                    if cue_re.search(sub_line):
                        i -= 1
                        break
                    # Strip basic HTML tags
                    clean_line = re.sub(r"<[^>]+>", "", sub_line).strip()
                    if clean_line:
                        text_lines.append(clean_line)
                    i += 1

                segment_text = " ".join(text_lines)
                if segment_text:
                    segments.append({
                        "start": start_sec,
                        "end": end_sec,
                        "text": segment_text,
                    })
                    current_texts.append(segment_text)
            i += 1

        full_text = " ".join(current_texts)
        return segments, full_text

    def _normalize_video_data(self, url: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Convert yt-dlp raw info into the unified normalized schema."""
        video_id = str(info.get("id") or "")
        description = info.get("description") or info.get("title") or ""

        # Creator information
        creator_username = info.get("uploader") or None
        creator_display = info.get("channel") or info.get("creator") or None
        creator_id = str(info.get("uploader_id")) if info.get("uploader_id") else None

        # Statistics
        views = info.get("view_count")
        likes = info.get("like_count")
        comments = info.get("comment_count")
        shares = info.get("repost_count")

        # Media and stream formats
        duration = info.get("duration")
        width = info.get("width")
        height = info.get("height")
        thumbnail = info.get("thumbnail")
        direct_url = info.get("url")

        formats_list = []
        for fmt in info.get("formats", []):
            if fmt.get("url"):
                formats_list.append({
                    "format_id": fmt.get("format_id"),
                    "url": fmt.get("url"),
                    "ext": fmt.get("ext"),
                    "width": fmt.get("width"),
                    "height": fmt.get("height"),
                    "vcodec": fmt.get("vcodec"),
                    "acodec": fmt.get("acodec"),
                })

        # Sound information
        sound_title = info.get("track") or info.get("alt_title") or "original sound"
        sound_author = info.get("artist") or creator_display or None

        return {
            "success": True,
            "platform": "tiktok",
            "url": url,
            "id": video_id,
            "description": description,
            "creator": {
                "username": creator_username,
                "display_name": creator_display,
                "id": creator_id,
                "avatar_url": None,
            },
            "statistics": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "downloads": 0,
                "favorites": None,
            },
            "video": {
                "duration": duration,
                "width": width,
                "height": height,
                "thumbnail_url": thumbnail,
                "direct_url": direct_url,
                "formats": formats_list,
            },
            "sound": {
                "title": sound_title,
                "author": sound_author,
                "id": None,
                "url": None,
            },
            "timestamp": str(info.get("timestamp")) if info.get("timestamp") else None,
            "raw": {},
        }
