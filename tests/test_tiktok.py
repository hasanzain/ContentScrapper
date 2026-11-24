import pytest
from scrapers.tiktok import TikTokScraper
from qa.comparator import QAComparator
from qa.metrics import QAMetricsCalculator
from qa.scrapecreator_adapter import ScrapeCreatorAdapter


def test_parse_time():
    """Unit test: parse VTT timestamps into float seconds."""
    assert TikTokScraper._parse_time("00:00:02.480") == 2.48
    assert TikTokScraper._parse_time("01:15.500") == 75.5
    assert TikTokScraper._parse_time("10.25") == 10.25


def test_parse_vtt():
    """Unit test: parse standard WEBVTT text into structured segments."""
    scraper = TikTokScraper()
    vtt = """WEBVTT

00:00:00.020 --> 00:00:02.480
Ladies and gentlemen, welcome!

00:00:02.620 --> 00:00:04.880
Explore the towering skyscrapers.
"""
    segments, full_text = scraper._parse_vtt(vtt)
    assert len(segments) == 2
    assert segments[0]["start"] == 0.02
    assert segments[0]["end"] == 2.48
    assert segments[0]["text"] == "Ladies and gentlemen, welcome!"
    assert segments[1]["start"] == 2.62
    assert "Explore the towering skyscrapers." in full_text


def test_normalize_local_video():
    """Unit test: verify normalization of yt-dlp metadata."""
    scraper = TikTokScraper()
    raw_info = {
        "id": "7703050842051579158",
        "title": "Welcome to New York",
        "description": "NYC travel guide",
        "uploader": "travel_guide",
        "channel": "Travel Guide NYC",
        "uploader_id": "999888777",
        "view_count": 100000,
        "like_count": 5000,
        "comment_count": 250,
        "repost_count": 50,
        "save_count": 300,
        "duration": 15,
        "width": 1080,
        "height": 1920,
        "thumbnail": "https://example.com/thumb.jpg",
        "url": "https://example.com/video.mp4",
        "track": "Original Sound",
        "artist": "Creator Music",
        "timestamp": 1700000000,
        "formats": [{"format_id": "0", "url": "https://example.com/stream.mp4"}],
    }

    norm = scraper._normalize_video_data("https://tiktok.com/@a/video/1", raw_info)
    assert norm["success"] is True
    assert norm["id"] == "7703050842051579158"
    assert norm["creator"]["username"] == "travel_guide"
    assert norm["statistics"]["views"] == 100000
    assert norm["video"]["duration"] == 15
    assert norm["sound"]["title"] == "Original Sound"
    assert len(norm["video"]["formats"]) == 1


def test_comparator_matches_and_tolerances():
    """Unit test: comparator handles exact matches, tolerances, and gaps."""
    comparator = QAComparator(dynamic_tolerance_pct=10.0)

    local = {
        "id": "123",
        "description": "Hello world",
        "creator": {"username": "user1", "id": "u1"},
        "statistics": {"views": 1000, "likes": 500, "comments": 10},
        "video": {"duration": 10, "direct_url": "https://cdn.local/video.mp4"},
        "sound": {"title": "Song"},
    }

    reference = {
        "id": "123",
        "description": "Hello world",
        "creator": {"username": "user1", "id": "u1", "avatar_url": "https://cdn.ref/avatar.jpg"},
        "statistics": {"views": 1050, "likes": 500, "comments": 50},  # views +5% (approx), comments +400% (mismatch)
        "video": {"duration": 10, "direct_url": "https://cdn.ref/video.mp4"},
        "sound": {"title": "Song"},
    }

    comp = comparator.compare(local_video=local, reference_video=reference)
    status_map = {f["field"]: f["status"] for f in comp["fields"]}

    assert status_map["video.id"] == "MATCH"
    assert status_map["creator.username"] == "MATCH"
    assert status_map["statistics.likes"] == "MATCH"
    assert status_map["statistics.views"] == "APPROXIMATE_MATCH"
    assert status_map["statistics.comments"] == "MISMATCH"
    assert status_map["creator.avatar_url"] == "REFERENCE_ONLY"


def test_metrics_calculation():
    """Unit test: metrics calculator correctly weights and calculates quality scores."""
    calc = QAMetricsCalculator()
    comp_result = {
        "fields": [
            {"field": "video.id", "status": "MATCH", "local": "1", "reference": "1"},
            {"field": "creator.username", "status": "MATCH", "local": "u", "reference": "u"},
            {"field": "statistics.views", "status": "APPROXIMATE_MATCH", "local": 100, "reference": 105},
            {"field": "video.duration", "status": "MATCH", "local": 10, "reference": 10},
            {"field": "transcript.available", "status": "MATCH", "local": True, "reference": True},
        ]
    }

    metrics = calc.calculate(comp_result)
    assert metrics["overall_score"] > 90.0
    assert metrics["coverage_percent"] == 100.0
    assert metrics["recommendation"] == "PASS"


def test_scrapecreator_adapter_normalization():
    """Unit test: adapter transforms raw ScrapeCreator structure to standard schema."""
    adapter = ScrapeCreatorAdapter()
    raw_sc = {
        "success": True,
        "aweme_detail": {
            "aweme_id": "7703050842051579158",
            "desc": "NYC Tour",
            "author": {"unique_id": "nyctour", "nickname": "NYC Tour Guide", "uid": "12345"},
            "statistics": {
                "play_count": 50000,
                "digg_count": 2000,
                "comment_count": 100,
                "share_count": 50,
                "collect_count": 120,
            },
            "video": {
                "duration": 15000,  # 15000 ms -> 15s
                "width": 1080,
                "height": 1920,
                "play_addr": {"url_list": ["https://cdn.tiktok/video.mp4"]},
            },
            "music": {"title": "Soundtrack", "author": "Artist", "id": "888"},
        },
    }

    norm = adapter.normalize_scrapecreator_video(raw_sc, url="https://tiktok.com/@nyctour/video/7703050842051579158")
    assert norm["success"] is True
    assert norm["id"] == "7703050842051579158"
    assert norm["video"]["duration"] == 15
    assert norm["creator"]["username"] == "nyctour"
    assert norm["statistics"]["views"] == 50000
    assert norm["sound"]["title"] == "Soundtrack"
