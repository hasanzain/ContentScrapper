import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class ScrapeCreatorAdapter:
    """Adapter to ingest, cache, and normalize ScrapeCreator reference MCP responses."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or Path(__file__).parent / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save_reference_fixture(
        self, video_id_or_key: str, data: Dict[str, Any]
    ) -> Path:
        """Save captured ScrapeCreator output to disk fixture cache."""
        clean_key = re.sub(r"[^\w\-_]", "_", video_id_or_key)
        path = self.cache_dir / f"scrapecreator_{clean_key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def load_reference_fixture(
        self, video_id_or_key: str
    ) -> Optional[Dict[str, Any]]:
        """Load cached ScrapeCreator output by key or ID."""
        clean_key = re.sub(r"[^\w\-_]", "_", video_id_or_key)
        path = self.cache_dir / f"scrapecreator_{clean_key}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def normalize_scrapecreator_video(
        self, raw_resp: Dict[str, Any], url: str = ""
    ) -> Dict[str, Any]:
        """Normalize ScrapeCreator v2_tiktok_video response into standard schema."""
        if not raw_resp or not raw_resp.get("success", False):
            return {
                "success": False,
                "platform": "tiktok",
                "url": url,
                "error": raw_resp.get("error") if raw_resp else "Empty response",
            }

        detail = raw_resp.get("aweme_detail") or {}
        video_id = str(detail.get("aweme_id") or "")
        description = detail.get("desc") or ""

        # Author / Creator
        author = detail.get("author") or {}
        creator_username = author.get("unique_id")
        creator_display = author.get("nickname")
        creator_id = str(author.get("uid")) if author.get("uid") else None

        avatar_url = None
        for av_key in ["avatar_larger", "avatar_medium", "avatar_thumb"]:
            av_obj = author.get(av_key)
            if isinstance(av_obj, dict) and av_obj.get("url_list"):
                avatar_url = av_obj["url_list"][0]
                break

        # Statistics
        stats = detail.get("statistics") or {}
        views = stats.get("play_count", 0)
        likes = stats.get("digg_count", 0)
        comments = stats.get("comment_count", 0)
        shares = stats.get("share_count", 0)
        downloads = stats.get("download_count", 0)
        favorites = stats.get("collect_count", 0)

        # Video media
        video_obj = detail.get("video") or {}
        raw_dur = video_obj.get("duration", 0)
        # TikTok aweme duration is often in milliseconds (> 1000)
        duration = int(round(raw_dur / 1000.0)) if raw_dur > 1000 else int(raw_dur)

        width = video_obj.get("width", 0)
        height = video_obj.get("height", 0)

        # Cover / Thumbnail
        thumbnail_url = None
        cover_obj = video_obj.get("cover") or video_obj.get("origin_cover") or {}
        if isinstance(cover_obj, dict) and cover_obj.get("url_list"):
            thumbnail_url = cover_obj["url_list"][0]

        # Direct video download / play URL
        direct_url = None
        dl_obj = (
            video_obj.get("download_no_watermark_addr")
            or video_obj.get("download_addr")
            or video_obj.get("play_addr")
            or {}
        )
        if isinstance(dl_obj, dict) and dl_obj.get("url_list"):
            direct_url = dl_obj["url_list"][0]

        # Sound
        music_obj = detail.get("music") or {}
        sound_id = str(music_obj.get("id")) if music_obj.get("id") else None
        sound_title = music_obj.get("title")
        sound_author = music_obj.get("author")
        sound_url = None
        play_url_obj = music_obj.get("play_url") or {}
        if isinstance(play_url_obj, dict) and play_url_obj.get("url_list"):
            sound_url = play_url_obj["url_list"][0]

        # Timestamp
        create_time = detail.get("create_time")
        timestamp = str(create_time) if create_time else None

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
                "avatar_url": avatar_url,
            },
            "statistics": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "downloads": downloads,
                "favorites": favorites,
            },
            "video": {
                "duration": duration,
                "width": width,
                "height": height,
                "thumbnail_url": thumbnail_url,
                "direct_url": direct_url,
                "formats": [],
            },
            "sound": {
                "title": sound_title,
                "author": sound_author,
                "id": sound_id,
                "url": sound_url,
            },
            "timestamp": timestamp,
            "raw": {
                "credits_charged": raw_resp.get("credits_charged"),
                "credits_remaining": raw_resp.get("credits_remaining"),
            },
        }

    def normalize_scrapecreator_transcript(
        self, raw_resp: Dict[str, Any], url: str = ""
    ) -> Dict[str, Any]:
        """Normalize ScrapeCreator transcript response into standard schema."""
        if not raw_resp or not raw_resp.get("success", False):
            return {
                "success": False,
                "platform": "tiktok",
                "url": url,
                "available": False,
                "segments": [],
                "text": "",
                "error": raw_resp.get("error") if raw_resp else "Empty transcript",
            }

        transcript_with_ts = raw_resp.get("transcript_with_timestamp") or []
        segments: List[Dict[str, Any]] = []
        for item in transcript_with_ts:
            segments.append({
                "start": round(float(item.get("start", 0)), 3),
                "end": round(float(item.get("end", 0)), 3),
                "text": str(item.get("text", "")).strip(),
            })

        full_text = " ".join(s["text"] for s in segments if s["text"]).strip()
        has_transcript = bool(segments or raw_resp.get("transcript"))

        return {
            "success": True,
            "platform": "tiktok",
            "url": url,
            "available": has_transcript,
            "language": raw_resp.get("language"),
            "segments": segments,
            "text": full_text,
        }
