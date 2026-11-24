import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class QAReporter:
    """Generates human-readable QA comparison reports and saves raw benchmark artifacts."""

    def __init__(self, results_dir: Optional[str] = None):
        self.results_dir = Path(results_dir or Path(__file__).parent / "results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        url: str,
        comparison: Dict[str, Any],
        metrics: Dict[str, Any],
        local_data: Optional[Dict[str, Any]] = None,
        reference_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Render a clean, formatted QA report string."""
        fields: List[Dict[str, Any]] = comparison.get("fields", [])
        overall_score = metrics.get("overall_score", 0.0)
        coverage = metrics.get("coverage_percent", 0.0)
        exact_rate = metrics.get("exact_match_rate", 0.0)
        approx_rate = metrics.get("approx_match_rate", 0.0)
        mismatch_rate = metrics.get("mismatch_rate", 0.0)
        rec = metrics.get("recommendation", "UNKNOWN")

        # Determine Local Advantages and Gaps
        advantages: List[str] = []
        gaps: List[str] = []

        for f in fields:
            fname = f["field"]
            st = f["status"]
            loc_val = f["local"]
            ref_val = f["reference"]

            if st == "LOCAL_ONLY":
                advantages.append(f"Local captured '{fname}' ({loc_val}) which reference lacked")
            elif st == "REFERENCE_ONLY":
                gaps.append(f"Reference captured '{fname}' ({ref_val}) which local lacked")
            elif st == "MISMATCH":
                gaps.append(f"Value mismatch on '{fname}': local={loc_val!r} vs ref={ref_val!r}")

        # Check direct formats availability
        if local_data and local_data.get("video", {}).get("formats"):
            num_formats = len(local_data["video"]["formats"])
            advantages.append(f"Local provides {num_formats} direct video format streams without watermarks")

        lines: List[str] = []
        lines.append("====================================================")
        lines.append("TikTok Scraper QA Report")
        lines.append("====================================================")
        lines.append("")
        lines.append(f"URL: {url}")
        lines.append("Reference: ScrapeCreator MCP")
        lines.append("Local:     Local TikTok MCP (yt-dlp engine)")
        lines.append("")
        lines.append("----------------------------------------------------")
        lines.append("OVERALL")
        lines.append("----------------------------------------------------")
        lines.append(f"Overall Score       : {overall_score} / 100")
        lines.append(f"Coverage            : {coverage}%")
        lines.append(f"Exact Match         : {exact_rate}%")
        lines.append(f"Approximate Match   : {approx_rate}%")
        lines.append(f"Mismatch            : {mismatch_rate}%")
        lines.append("")
        lines.append("Subscores:")
        scores = metrics.get("scores", {})
        for sname, sval in scores.items():
            nice_name = sname.replace("_score", "").capitalize()
            lines.append(f"  - {nice_name:<16}: {sval}%")
        lines.append("")
        lines.append("----------------------------------------------------")
        lines.append("FIELD COMPARISON")
        lines.append("----------------------------------------------------")
        lines.append(f"{'Field':<24} {'Local':<18} {'Reference':<18} {'Status'}")
        lines.append("-" * 68)

        for f in fields:
            fname = f["field"]
            loc_str = self._format_val(f["local"])
            ref_str = self._format_val(f["reference"])
            st = f["status"]
            lines.append(f"{fname:<24} {loc_str:<18} {ref_str:<18} {st}")

        lines.append("")
        lines.append("----------------------------------------------------")
        lines.append("LOCAL ADVANTAGES")
        lines.append("----------------------------------------------------")
        if advantages:
            for adv in advantages:
                lines.append(f"- {adv}")
        else:
            lines.append("- None noted.")

        lines.append("")
        lines.append("----------------------------------------------------")
        lines.append("LOCAL GAPS")
        lines.append("----------------------------------------------------")
        if gaps:
            for gap in gaps:
                lines.append(f"- {gap}")
        else:
            lines.append("- None noted (100% parity on available fields).")

        lines.append("")
        lines.append("----------------------------------------------------")
        lines.append("RECOMMENDATION")
        lines.append("----------------------------------------------------")
        lines.append(rec)
        lines.append("====================================================")

        return "\n".join(lines)

    def save_raw_result(
        self,
        url: str,
        video_id: str,
        local_data: Dict[str, Any],
        reference_data: Dict[str, Any],
        comparison: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Path:
        """Persist structured benchmark outcome to disk."""
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = "".join(c for c in str(video_id) if c.isalnum() or c in ("-", "_")) or "unknown"
        filename = f"{now_str}-{safe_id}.json"
        target_path = self.results_dir / filename

        artifact = {
            "test": {
                "timestamp": datetime.datetime.now().isoformat(),
                "url": url,
                "video_id": video_id,
            },
            "local": local_data,
            "reference": reference_data,
            "comparison": comparison,
            "metrics": metrics,
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)

        return target_path

    @staticmethod
    def _format_val(val: Any) -> str:
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, (int, float)):
            return str(val)
        val_str = str(val).strip()
        if len(val_str) > 15:
            return val_str[:12] + "..."
        return val_str
