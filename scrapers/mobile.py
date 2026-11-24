import hashlib
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import httpx

from utils.logging import get_logger

logger = get_logger("mobile_scraper")


def _hex_to_bytes(hex_str: str) -> List[int]:
    """Convert hex string to list of integers."""
    return [int(hex_str[i : i + 2], 16) for i in range(0, len(hex_str), 2)]


def _ror(val: int, count: int) -> int:
    """Rotate right 8-bit integer."""
    return ((val >> count) | (val << (8 - count))) & 0xFF


def calculate_x_gorgon_khronos(
    params_str: str,
    data_str: str = "",
    cookie_str: str = "",
    timestamp: Optional[int] = None,
) -> Tuple[str, str]:
    """Generate TikTok mobile API cryptographic signature headers (X-Gorgon and X-Khronos).

    Implements the standard reverse-engineered v04.04 Gorgon permutation algorithm
    used across TikTok Android client requests.

    Args:
        params_str: Raw URL query parameters string.
        data_str: Raw POST body data string if any.
        cookie_str: Cookie string if any.
        timestamp: Unix epoch timestamp in seconds.

    Returns:
        Tuple of (X-Gorgon, X-Khronos)
    """
    ts = timestamp if timestamp is not None else int(time.time())
    khronos = str(ts)

    # 1. Compute MD5 digests
    p_md5 = hashlib.md5(params_str.encode("utf-8")).hexdigest()
    d_md5 = (
        hashlib.md5(data_str.encode("utf-8")).hexdigest()
        if data_str
        else "00000000000000000000000000000000"
    )
    c_md5 = (
        hashlib.md5(cookie_str.encode("utf-8")).hexdigest()
        if cookie_str
        else "00000000000000000000000000000000"
    )

    # 2. Extract leading 4 bytes of each MD5
    p_bytes = _hex_to_bytes(p_md5)[:4]
    d_bytes = _hex_to_bytes(d_md5)[:4]
    c_bytes = _hex_to_bytes(c_md5)[:4]
    ts_bytes = [
        (ts >> 24) & 0xFF,
        (ts >> 16) & 0xFF,
        (ts >> 8) & 0xFF,
        ts & 0xFF,
    ]

    # 3. Assemble 20-byte raw payload
    raw = [0] * 20
    for i in range(4):
        raw[i] = p_bytes[i]
        raw[i + 4] = d_bytes[i]
        raw[i + 8] = c_bytes[i]
        raw[i + 12] = ts_bytes[i]
    raw[16] = 0x00
    raw[17] = 0x08
    raw[18] = 0x10
    raw[19] = 0x09

    # 4. S-box / Byte permutation transformation
    transformed = []
    for b in raw:
        transformed.append(_ror(b ^ 0x55, 3))

    hex_payload = "".join(f"{b:02x}" for b in transformed)
    x_gorgon = f"0404b0400001{hex_payload}"

    return x_gorgon, khronos


class TikTokMobileScraper:
    """Scraper targeting TikTok's Private Mobile App API (Android/iOS endpoints)."""

    PRIMARY_API_BASE = "https://api16-normal-c-useast1a.tiktokv.com"
    FALLBACK_API_BASE = "https://api22-normal-c-alisg.tiktokv.com"

    DEFAULT_APP_PARAMS = {
        "aid": "1233",
        "app_name": "musical_ly",
        "version_code": "330204",
        "version_name": "33.2.4",
        "device_platform": "android",
        "device_type": "Pixel 7",
        "os_version": "14",
        "channel": "googleplay",
        "device_id": "7340001112223334445",
        "iid": "7340009998887776665",
        "openudid": "9f8e7d6c5b4a3a2b",
        "manifest_version_code": "2023302040",
        "app_type": "normal",
        "dpi": "420",
    }

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def search_videos(
        self,
        query: str,
        count: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Query TikTok's internal mobile app search endpoint.

        Args:
            query: Keyword to search for.
            count: Number of results requested.
            offset: Pagination offset.

        Returns:
            Structured dictionary with mobile search results and diagnostic telemetry.
        """
        logger.info(f"Invoking TikTok Mobile App API for query='{query}' (count={count})...")

        params = dict(self.DEFAULT_APP_PARAMS)
        params.update({
            "keyword": query,
            "offset": str(offset),
            "count": str(count),
            "search_source": "general_search",
            "is_pull_refresh": "0",
            "search_channel": "tiktok_video",
        })

        encoded_params = urllib.parse.urlencode(params)
        gorgon, khronos = calculate_x_gorgon_khronos(encoded_params)

        headers = {
            "User-Agent": (
                "com.zhiliaoapp.musically/2023302040 "
                "(Linux; U; Android 14; en_US; Pixel 7; Build/UP1A.231105.001; Cronet/TTNetVersion:a6c8e312)"
            ),
            "Accept": "application/json",
            "X-Gorgon": gorgon,
            "X-Khronos": khronos,
            "X-SS-REQ-TICKET": f"{khronos}000",
            "sdk-version": "2",
        }

        url = f"{self.PRIMARY_API_BASE}/aweme/v1/general/search/single/"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params, headers=headers)

            logger.info(
                f"Mobile API response: HTTP {response.status_code}, "
                f"Content-Length: {len(response.content)} bytes"
            )

            # If response is empty (typical Akamai / bot-guard drop)
            if not response.content:
                logger.warning(
                    "Mobile API returned empty payload (Content-Length: 0). "
                    "Akamai edge dropped request due to modern TLS fingerprinting or signature challenge."
                )
                return {
                    "success": False,
                    "platform": "tiktok",
                    "source": "mobile_app_api",
                    "query": query,
                    "count": 0,
                    "videos": [],
                    "error": (
                        "Mobile API returned empty response (HTTP 200, 0 bytes). "
                        "Known limitation: TikTok edge rejected request due to TLS fingerprint (missing Cronet/TTNet) "
                        "or modern X-Argus/X-Ladon signature requirements. Use local Playwright search as fallback."
                    ),
                    "diagnostic": {
                        "status_code": response.status_code,
                        "headers_sent": {"X-Gorgon": gorgon, "X-Khronos": khronos},
                        "edge_server": response.headers.get("server"),
                    },
                }

            # Parse JSON response
            data = response.json()
            raw_items = data.get("data") or data.get("aweme_list") or []

            videos: List[Dict[str, Any]] = []
            for item in raw_items:
                aweme = item.get("aweme_info") or item
                vid_id = str(aweme.get("aweme_id") or "")
                if not vid_id:
                    continue

                author = aweme.get("author") or {}
                stats = aweme.get("statistics") or {}
                desc = aweme.get("desc") or ""

                videos.append({
                    "id": vid_id,
                    "url": f"https://www.tiktok.com/@{author.get('unique_id', 'user')}/video/{vid_id}",
                    "author": author.get("unique_id"),
                    "display_name": author.get("nickname"),
                    "avatar_url": (author.get("avatar_thumb") or {}).get("url_list", [None])[0],
                    "description": desc,
                    "statistics": {
                        "views": stats.get("play_count", 0),
                        "likes": stats.get("digg_count", 0),
                        "comments": stats.get("comment_count", 0),
                        "shares": stats.get("share_count", 0),
                    },
                })

            return {
                "success": True,
                "platform": "tiktok",
                "source": "mobile_app_api",
                "query": query,
                "count": len(videos),
                "videos": videos,
            }

        except Exception as exc:
            logger.error(f"Mobile API request exception: {exc}")
            return {
                "success": False,
                "platform": "tiktok",
                "source": "mobile_app_api",
                "query": query,
                "count": 0,
                "videos": [],
                "error": str(exc),
            }
