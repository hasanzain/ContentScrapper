import sys
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from scrapers.tiktok import TikTokScraper
from scrapers.search import TikTokSearchScraper
from scrapers.mobile import TikTokMobileScraper
from utils.logging import get_logger

logger = get_logger("server")

# Initialize FastMCP Server
mcp = FastMCP(
    "content-scrapper",
    dependencies=["yt-dlp", "httpx", "playwright"],
)

# Global scraper instances
_scraper = TikTokScraper()
_search_scraper = TikTokSearchScraper()
_mobile_scraper = TikTokMobileScraper()


@mcp.tool()
def scrape_tiktok_video(url: str) -> Dict[str, Any]:
    """Scrapes public TikTok video metadata without downloading physical media.

    Args:
        url: The public TikTok video URL (e.g. https://www.tiktok.com/@user/video/1234567890)

    Returns:
        Structured normalized dictionary with id, description, creator, statistics, video, sound, etc.
    """
    logger.info(f"Tool invocation: scrape_tiktok_video for '{url}'")
    try:
        result = _scraper.scrape_video(url)
        return result
    except Exception as exc:
        logger.error(f"Error in scrape_tiktok_video tool: {exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "url": url,
            "error": str(exc),
        }


@mcp.tool()
def get_tiktok_transcript(url: str) -> Dict[str, Any]:
    """Retrieves subtitles and timestamped transcript segments for a TikTok video.

    Args:
        url: The public TikTok video URL

    Returns:
        Dictionary with success, available, language, segments list, and full plain text.
    """
    logger.info(f"Tool invocation: get_tiktok_transcript for '{url}'")
    try:
        result = _scraper.get_transcript(url)
        return result
    except Exception as exc:
        logger.error(f"Error in get_tiktok_transcript tool: {exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "url": url,
            "available": False,
            "segments": [],
            "text": "",
            "error": str(exc),
        }


@mcp.tool()
async def search_tiktok_videos(query: str, count: int = 10) -> Dict[str, Any]:
    """Searches TikTok for viral videos matching a keyword or phrase without API credits.

    Args:
        query: Search keyword or phrase (e.g. "resep viral", "mukbang", "tips bisnis").
        count: Desired number of video results (default: 10, max: 30).

    Returns:
        Structured dictionary containing list of discovered videos with IDs, URLs, authors, and captions.
    """
    logger.info(f"Tool invocation: search_tiktok_videos for query='{query}' (count={count})")
    try:
        result = await _search_scraper.search_videos(query=query, count=count)
        return result
    except Exception as exc:
        logger.error(f"Error in search_tiktok_videos tool: {exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "query": query,
            "count": 0,
            "videos": [],
            "error": str(exc),
        }


@mcp.tool()
def search_tiktok_mobile(query: str, count: int = 10) -> Dict[str, Any]:
    """Queries TikTok's internal Mobile App API using simulated Android signatures (X-Gorgon/Khronos).

    Args:
        query: Search keyword or phrase.
        count: Desired number of video results (default: 10).

    Returns:
        Structured dictionary with mobile search items, or diagnostic telemetry if edge blocked.
    """
    logger.info(f"Tool invocation: search_tiktok_mobile for query='{query}' (count={count})")
    try:
        result = _mobile_scraper.search_videos(query=query, count=count)
        return result
    except Exception as exc:
        logger.error(f"Error in search_tiktok_mobile tool: {exc}")
        return {
            "success": False,
            "platform": "tiktok",
            "source": "mobile_app_api",
            "query": query,
            "count": 0,
            "videos": [],
            "error": str(exc),
        }


if __name__ == "__main__":
    logger.info("Starting TikTok Scraper MCP server over stdio transport...")
    mcp.run(transport="stdio")
