from typing import Any, Dict, List


class QAMetricsCalculator:
    """Calculates granular quality and comparative metrics from field comparison results."""

    def __init__(
        self,
        weight_metadata: float = 0.40,
        weight_statistics: float = 0.25,
        weight_creator: float = 0.15,
        weight_media: float = 0.10,
        weight_transcript: float = 0.10,
    ):
        self.w_meta = weight_metadata
        self.w_stats = weight_statistics
        self.w_creator = weight_creator
        self.w_media = weight_media
        self.w_transcript = weight_transcript

    def calculate(self, comparison_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all rates, subscores, and overall quality score."""
        fields: List[Dict[str, Any]] = comparison_result.get("fields", [])

        status_counts = {
            "MATCH": 0,
            "APPROXIMATE_MATCH": 0,
            "MISMATCH": 0,
            "LOCAL_ONLY": 0,
            "REFERENCE_ONLY": 0,
            "BOTH_MISSING": 0,
            "UNCOMPARABLE": 0,
        }

        ref_available_count = 0
        local_available_count = 0

        # Sub-category buckets
        buckets = {
            "metadata": [],
            "statistics": [],
            "creator": [],
            "media": [],
            "transcript": [],
        }

        for f in fields:
            st = f.get("status", "UNCOMPARABLE")
            status_counts[st] = status_counts.get(st, 0) + 1

            loc_has = st not in {"REFERENCE_ONLY", "BOTH_MISSING", "UNCOMPARABLE"}
            ref_has = st not in {"LOCAL_ONLY", "BOTH_MISSING", "UNCOMPARABLE"}

            if loc_has:
                local_available_count += 1
            if ref_has:
                ref_available_count += 1

            fname = f.get("field", "")
            if fname.startswith("statistics."):
                buckets["statistics"].append(f)
            elif fname.startswith("creator."):
                buckets["creator"].append(f)
            elif fname.startswith("video."):
                buckets["media"].append(f)
            elif fname.startswith("transcript."):
                buckets["transcript"].append(f)
            else:
                buckets["metadata"].append(f)

        # Base counts
        matches = status_counts["MATCH"]
        approx = status_counts["APPROXIMATE_MATCH"]
        mismatches = status_counts["MISMATCH"]
        comparable_count = matches + approx + mismatches

        exact_match_rate = (
            round((matches / comparable_count) * 100.0, 1)
            if comparable_count > 0
            else 0.0
        )
        approx_match_rate = (
            round((approx / comparable_count) * 100.0, 1)
            if comparable_count > 0
            else 0.0
        )
        mismatch_rate = (
            round((mismatches / comparable_count) * 100.0, 1)
            if comparable_count > 0
            else 0.0
        )

        coverage = (
            round((local_available_count / ref_available_count) * 100.0, 1)
            if ref_available_count > 0
            else 100.0
        )

        # Subscore calculations (0 to 100)
        metadata_score = self._score_bucket(buckets["metadata"])
        statistics_score = self._score_bucket(buckets["statistics"])
        creator_score = self._score_bucket(buckets["creator"])
        media_score = self._score_bucket(buckets["media"])
        transcript_score = self._score_bucket(buckets["transcript"])

        overall_score = round(
            (metadata_score * self.w_meta)
            + (statistics_score * self.w_stats)
            + (creator_score * self.w_creator)
            + (media_score * self.w_media)
            + (transcript_score * self.w_transcript),
            1,
        )

        # Completeness score: proportion of known standard schema fields populated
        total_possible = len(fields)
        populated_local = sum(1 for f in fields if f.get("local") not in (None, "", [], 0))
        completeness_score = (
            round((populated_local / total_possible) * 100.0, 1)
            if total_possible > 0
            else 0.0
        )

        # Accuracy score: proportion of comparable fields that match (exact or approx)
        accuracy_score = (
            round(((matches + approx) / comparable_count) * 100.0, 1)
            if comparable_count > 0
            else 0.0
        )

        # Recommendation determination
        critical_mismatch = any(
            f["field"] in {"video.id", "creator.username"} and f["status"] == "MISMATCH"
            for f in fields
        )

        if overall_score >= 80.0 and not critical_mismatch:
            recommendation = "PASS"
        elif overall_score >= 50.0:
            recommendation = "NEED IMPROVEMENT"
        else:
            recommendation = "FAIL"

        return {
            "overall_score": overall_score,
            "coverage_percent": coverage,
            "exact_match_rate": exact_match_rate,
            "approx_match_rate": approx_match_rate,
            "mismatch_rate": mismatch_rate,
            "scores": {
                "coverage_score": coverage,
                "accuracy_score": accuracy_score,
                "completeness_score": completeness_score,
                "metadata_score": metadata_score,
                "statistics_score": statistics_score,
                "creator_score": creator_score,
                "media_score": media_score,
                "transcript_score": transcript_score,
            },
            "counts": status_counts,
            "comparable_count": comparable_count,
            "local_available": local_available_count,
            "reference_available": ref_available_count,
            "recommendation": recommendation,
        }

    def _score_bucket(self, field_list: List[Dict[str, Any]]) -> float:
        """Score a category of fields: MATCH=1.0, APPROXIMATE=0.9, LOCAL_ONLY=0.8, MISMATCH=0.0."""
        if not field_list:
            return 100.0

        points = 0.0
        weight = 0.0

        for f in field_list:
            st = f.get("status")
            if st == "BOTH_MISSING":
                continue
            weight += 1.0
            if st == "MATCH":
                points += 1.0
            elif st == "APPROXIMATE_MATCH":
                points += 0.9
            elif st == "LOCAL_ONLY":
                points += 0.8  # Bonus for local advantage
            elif st == "REFERENCE_ONLY":
                points += 0.0
            elif st == "MISMATCH":
                points += 0.0

        if weight == 0.0:
            return 100.0
        return round((points / weight) * 100.0, 1)
