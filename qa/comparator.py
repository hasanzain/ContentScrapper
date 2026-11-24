import math
from typing import Any, Dict, List, Optional, Tuple

STATIC_FIELDS = {
    "video.id",
    "creator.username",
    "creator.id",
    "creator.display_name",
    "video.duration",
    "video.description",
    "video.width",
    "video.height",
    "video.thumbnail_url",
    "video.direct_url",
    "sound.id",
    "sound.title",
    "sound.author",
    "transcript.available",
    "transcript.text",
    "transcript.segments_count",
}

DYNAMIC_FIELDS = {
    "statistics.views",
    "statistics.likes",
    "statistics.comments",
    "statistics.shares",
    "statistics.favorites",
    "statistics.downloads",
}


class QAComparator:
    """Field-by-field comparative engine between local scraper and reference scraper."""

    def __init__(self, dynamic_tolerance_pct: float = 15.0):
        self.dynamic_tolerance_pct = dynamic_tolerance_pct

    def compare(
        self,
        local_video: Dict[str, Any],
        reference_video: Dict[str, Any],
        local_transcript: Optional[Dict[str, Any]] = None,
        reference_transcript: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform deep field-by-field comparison between local and reference results."""
        flat_local = self._flatten(local_video, local_transcript)
        flat_ref = self._flatten(reference_video, reference_transcript)

        all_fields = sorted(list(set(flat_local.keys()) | set(flat_ref.keys())))
        field_results: List[Dict[str, Any]] = []

        for field in all_fields:
            loc_val = flat_local.get(field)
            ref_val = flat_ref.get(field)
            is_dynamic = field in DYNAMIC_FIELDS
            field_type = "DYNAMIC" if is_dynamic else "STATIC"

            status, diff, diff_pct = self._compare_values(
                field, loc_val, ref_val, is_dynamic
            )

            field_results.append({
                "field": field,
                "local": loc_val,
                "reference": ref_val,
                "status": status,
                "type": field_type,
                "difference": diff,
                "difference_percent": diff_pct,
            })

        return {
            "fields": field_results,
            "url": local_video.get("url") or reference_video.get("url"),
            "video_id": local_video.get("id") or reference_video.get("id"),
        }

    def _compare_values(
        self, field: str, loc: Any, ref: Any, is_dynamic: bool
    ) -> Tuple[str, Optional[float], Optional[float]]:
        loc_empty = loc is None or loc == "" or loc == []
        ref_empty = ref is None or ref == "" or ref == []

        if loc_empty and ref_empty:
            return "BOTH_MISSING", None, None
        if loc_empty and not ref_empty:
            return "REFERENCE_ONLY", None, None
        if not loc_empty and ref_empty:
            return "LOCAL_ONLY", None, None

        # Special handling for direct URLs & thumbnails: existence check if URLs differ
        if field in {"video.direct_url", "video.thumbnail_url"}:
            if bool(loc) and bool(ref):
                return "MATCH", None, None
            return "MISMATCH", None, None

        # Special handling for duration: +/- 2 seconds allowed due to int vs float ms rounding
        if field == "video.duration":
            try:
                l_dur, r_dur = float(loc), float(ref)
                if abs(l_dur - r_dur) <= 2.0:
                    return "MATCH", abs(l_dur - r_dur), None
                return "MISMATCH", abs(l_dur - r_dur), None
            except (ValueError, TypeError):
                pass

        # Special handling for description / text: partial/substring match check
        if field in {"video.description", "transcript.text"} and isinstance(loc, str) and isinstance(ref, str):
            clean_l = loc.strip().lower()
            clean_r = ref.strip().lower()
            if clean_l == clean_r:
                return "MATCH", None, None
            if clean_l.startswith(clean_r[:50]) or clean_r.startswith(clean_l[:50]):
                return "APPROXIMATE_MATCH", None, None
            return "MISMATCH", None, None

        # Dynamic / numeric fields tolerance check
        if is_dynamic:
            try:
                l_num = float(loc)
                r_num = float(ref)
                diff = abs(l_num - r_num)
                max_val = max(l_num, r_num, 1.0)
                diff_pct = round((diff / max_val) * 100.0, 3)

                if diff == 0:
                    return "MATCH", 0.0, 0.0
                if diff_pct <= self.dynamic_tolerance_pct or diff <= 5:
                    return "APPROXIMATE_MATCH", diff, diff_pct
                return "MISMATCH", diff, diff_pct
            except (ValueError, TypeError):
                return "UNCOMPARABLE", None, None

        # Static field exact equality check
        if loc == ref:
            return "MATCH", None, None

        # Special handling for sound.title: prefix/substring match check (e.g. "original sound" vs "original sound - user")
        if field == "sound.title" and isinstance(loc, str) and isinstance(ref, str):
            clean_l = loc.strip().lower()
            clean_r = ref.strip().lower()
            if clean_l == clean_r:
                return "MATCH", None, None
            if clean_l in clean_r or clean_r in clean_l:
                return "APPROXIMATE_MATCH", None, None

        # Special handling for video dimensions: check if aspect ratio is identical (e.g. 1080x1920 vs 576x1024)
        if field in {"video.width", "video.height"}:
            try:
                l_num, r_num = float(loc), float(ref)
                if l_num == r_num:
                    return "MATCH", 0.0, 0.0
                # If both are valid video resolutions with proportional scaling (2x / 0.5x)
                ratio = max(l_num, r_num) / max(min(l_num, r_num), 1.0)
                if abs(ratio - 1.875) < 0.1 or abs(ratio - 2.0) < 0.1:  # 1080/576 = 1.875
                    return "APPROXIMATE_MATCH", abs(l_num - r_num), round(abs(l_num - r_num) / max(l_num, r_num) * 100, 1)
            except (ValueError, TypeError):
                pass

        # String case-insensitive comparison
        if isinstance(loc, str) and isinstance(ref, str):
            if loc.strip().lower() == ref.strip().lower():
                return "MATCH", None, None

        return "MISMATCH", None, None

    def _flatten(
        self,
        video_data: Dict[str, Any],
        transcript_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Flatten structured video & transcript dictionaries into dot-notated dictionary."""
        out: Dict[str, Any] = {}
        if not video_data:
            return out

        out["video.id"] = video_data.get("id")
        out["video.description"] = video_data.get("description")

        creator = video_data.get("creator") or {}
        out["creator.username"] = creator.get("username")
        out["creator.display_name"] = creator.get("display_name")
        out["creator.id"] = creator.get("id")
        out["creator.avatar_url"] = creator.get("avatar_url")

        stats = video_data.get("statistics") or {}
        out["statistics.views"] = stats.get("views")
        out["statistics.likes"] = stats.get("likes")
        out["statistics.comments"] = stats.get("comments")
        out["statistics.shares"] = stats.get("shares")
        out["statistics.downloads"] = stats.get("downloads")
        out["statistics.favorites"] = stats.get("favorites")

        video = video_data.get("video") or {}
        out["video.duration"] = video.get("duration")
        out["video.width"] = video.get("width")
        out["video.height"] = video.get("height")
        out["video.thumbnail_url"] = video.get("thumbnail_url")
        out["video.direct_url"] = video.get("direct_url")

        sound = video_data.get("sound") or {}
        out["sound.id"] = sound.get("id")
        out["sound.title"] = sound.get("title")
        out["sound.author"] = sound.get("author")

        if transcript_data:
            out["transcript.available"] = transcript_data.get("available")
            out["transcript.text"] = transcript_data.get("text")
            out["transcript.segments_count"] = len(transcript_data.get("segments") or [])

        return out
