from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseScraper(ABC):
    """Abstract base class for video platform scrapers."""

    @abstractmethod
    def scrape_video(self, url: str) -> Dict[str, Any]:
        """Extract metadata for a single video without downloading physical media."""
        pass

    @abstractmethod
    def get_transcript(self, url: str) -> Dict[str, Any]:
        """Extract subtitles/transcript for a single video."""
        pass
