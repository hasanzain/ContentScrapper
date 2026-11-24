from typing import Any, Dict, List, Optional
from pathlib import Path

from scrapers.tiktok import TikTokScraper
from qa.scrapecreator_adapter import ScrapeCreatorAdapter
from qa.comparator import QAComparator
from qa.metrics import QAMetricsCalculator
from qa.reporter import QAReporter
from utils.logging import get_logger

logger = get_logger("qa_runner")


class QARunner:
    """Orchestrates end-to-end comparative benchmarking between Local and ScrapeCreator."""

    def __init__(
        self,
        local_scraper: Optional[TikTokScraper] = None,
        adapter: Optional[ScrapeCreatorAdapter] = None,
        comparator: Optional[QAComparator] = None,
        metrics_calc: Optional[QAMetricsCalculator] = None,
        reporter: Optional[QAReporter] = None,
    ):
        self.local_scraper = local_scraper or TikTokScraper()
        self.adapter = adapter or ScrapeCreatorAdapter()
        self.comparator = comparator or QAComparator()
        self.metrics_calc = metrics_calc or QAMetricsCalculator()
        self.reporter = reporter or QAReporter()

    def run_benchmark(
        self,
        url: str,
        raw_reference_video: Optional[Dict[str, Any]] = None,
        raw_reference_transcript: Optional[Dict[str, Any]] = None,
        fixture_key: Optional[str] = None,
        save_artifact: bool = True,
    ) -> Dict[str, Any]:
        """Execute complete comparative QA cycle for a single TikTok URL."""
        logger.info(f"Running comparative QA for '{url}'...")

        # 1. Scrape via Local Scraper
        local_video = self.local_scraper.scrape_video(url)
        local_transcript = self.local_scraper.get_transcript(url)

        # 2. Acquire Reference Data (from parameters, or fixture cache)
        if not raw_reference_video and fixture_key:
            cached = self.adapter.load_reference_fixture(fixture_key)
            if cached:
                raw_reference_video = cached.get("video")
                raw_reference_transcript = cached.get("transcript")

        if not raw_reference_video:
            # Try to load fixture using video ID
            vid_id = local_video.get("id")
            if vid_id:
                cached = self.adapter.load_reference_fixture(vid_id)
                if cached:
                    raw_reference_video = cached.get("video")
                    raw_reference_transcript = cached.get("transcript")

        # 3. Normalize Reference Data
        if raw_reference_video:
            ref_video = self.adapter.normalize_scrapecreator_video(raw_reference_video, url=url)
        else:
            ref_video = {"success": False, "error": "No reference data provided"}

        if raw_reference_transcript:
            ref_transcript = self.adapter.normalize_scrapecreator_transcript(raw_reference_transcript, url=url)
        else:
            ref_transcript = {"success": False, "available": False, "segments": [], "text": ""}

        # 4. Compare Fields
        comparison = self.comparator.compare(
            local_video=local_video,
            reference_video=ref_video,
            local_transcript=local_transcript,
            reference_transcript=ref_transcript,
        )

        # 5. Compute Metrics
        metrics = self.metrics_calc.calculate(comparison)

        # 6. Generate Human-Readable Report
        report_text = self.reporter.generate_report(
            url=url,
            comparison=comparison,
            metrics=metrics,
            local_data=local_video,
            reference_data=ref_video,
        )

        # 7. Persist Artifact
        artifact_path = None
        if save_artifact:
            video_id = local_video.get("id") or ref_video.get("id") or "unknown"
            artifact_path = self.reporter.save_raw_result(
                url=url,
                video_id=video_id,
                local_data=local_video,
                reference_data=ref_video,
                comparison=comparison,
                metrics=metrics,
            )

        return {
            "url": url,
            "local_video": local_video,
            "local_transcript": local_transcript,
            "reference_video": ref_video,
            "reference_transcript": ref_transcript,
            "comparison": comparison,
            "metrics": metrics,
            "report": report_text,
            "artifact_path": str(artifact_path) if artifact_path else None,
        }
