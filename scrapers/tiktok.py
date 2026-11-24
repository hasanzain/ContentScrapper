import re
import urllib.request
from typing import Any, Dict, List, Optional
import yt_dlp

from scrapers.base import BaseScraper
from utils.logging import get_logger, YtDlpStderrLogger

logger = get_logger("tiktok_scraper")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


class TikTokScraper(BaseScraper):
    """TikTok scraper powered by yt-dlp metadata extraction."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Referer": "https://www.tiktok.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_ydl_opts(self) -> Dict[str, Any]:
        return {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "http_headers": self.headers,
            "logger": YtDlpStderrLogger(),
            "extract_flat": False,
        }

    def scrape_video(self, url: str) -> Dict[str, Any]:
        """Extract metadata for a TikTok video without downloading physical media."""
        try:
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
                return self._normalize_video_data(url, info)
        except Exception as exc:
            logger.error(f"Error scraping TikTok video '{url}': {exc}")
            return {
                "success": False,
                "platform": "tiktok",
                "url": url,
                "error": str(exc),
            }

    def get_transcript(self, url: str) -> Dict[str, Any]:
        """Extract transcript/captions for a TikTok video."""
        try:
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
                    return {
                        "success": True,
                        "platform": "tiktok",
                        "url": url,
                        "available": False,
                        "language": None,
                        "segments": [],
                        "text": "",
                    }

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
                    return {
                        "success": True,
                        "platform": "tiktok",
                        "url": url,
                        "available": False,
                        "language": None,
                        "segments": [],
                        "text": "",
                    }

                # Fetch and parse subtitle content
                vtt_text = self._fetch_url_content(chosen_url)
                segments, full_text = self._parse_vtt(vtt_text)

                return {
                    "success": True,
                    "platform": "tiktok",
                    "url": url,
                    "available": len(segments) > 0,
                    "language": chosen_lang,
                    "segments": segments,
                    "text": full_text,
                }
        except Exception as exc:
            logger.error(f"Error getting transcript for '{url}': {exc}")
            return {
                "success": False,
                "platform": "tiktok",
                "url": url,
                "available": False,
                "segments": [],
                "text": "",
                "error": str(exc),
            }

    def _fetch_url_content(self, url: str) -> str:
        req = urllib.request.Request(url, headers=self.headers)
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
        favorites = info.get("save_count")

        # Video media details
        duration = info.get("duration")
        width = info.get("width")
        height = info.get("height")
        thumbnail_url = info.get("thumbnail")
        direct_url = info.get("url")

        # Formats list
        raw_formats = info.get("formats") or []
        formats: List[Dict[str, Any]] = []
        for f in raw_formats:
            formats.append({
                "format_id": f.get("format_id"),
                "url": f.get("url"),
                "ext": f.get("ext"),
                "width": f.get("width"),
                "height": f.get("height"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "filesize": f.get("filesize"),
                "quality": f.get("quality"),
            })

        # Sound information
        sound_title = info.get("track")
        sound_author = info.get("artist")
        sound_id = None
        sound_url = None

        timestamp = None
        if info.get("timestamp"):
            timestamp = str(info.get("timestamp"))
        elif info.get("upload_date"):
            timestamp = str(info.get("upload_date"))

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
                "views": views if views is not None else 0,
                "likes": likes if likes is not None else 0,
                "comments": comments if comments is not None else 0,
                "shares": shares if shares is not None else 0,
                "downloads": 0,
                "favorites": favorites if favorites is not None else 0,
            },
            "video": {
                "duration": duration if duration is not None else 0,
                "width": width if width is not None else 0,
                "height": height if height is not None else 0,
                "thumbnail_url": thumbnail_url,
                "direct_url": direct_url,
                "formats": formats,
            },
            "sound": {
                "title": sound_title,
                "author": sound_author,
                "id": sound_id,
                "url": sound_url,
            },
            "timestamp": timestamp,
            "raw": {
                "extractor": info.get("extractor"),
                "webpage_url": info.get("webpage_url"),
                "subtitles": list((info.get("subtitles") or {}).keys()),
            },
        }
