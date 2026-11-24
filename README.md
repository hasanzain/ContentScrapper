# TikTok Scraper MCP & Comparative QA Benchmark

A self-hosted, lightweight Model Context Protocol (MCP) server for scraping TikTok video metadata, statistics, and timestamped transcripts, paired with an automated comparative QA benchmark engine that evaluates local performance against ScrapeCreator MCP.

---

## 1. Project Overview

This project provides:
1. **Local TikTok MCP Server**: A zero-credit, self-hosted FastMCP server that extracts rich video metadata and timestamped transcripts using `yt-dlp` without downloading physical video media.
2. **QA & Comparative Benchmark Engine**: A field-by-field verification system that compares local extraction results against reference scraper implementations (specifically ScrapeCreator MCP) on the exact same URLs.
3. **Structured Metrics & Reporting**: Computes coverage, exact match rate, dynamic tolerance variance, completeness, and overall quality score with pass/fail recommendations.

---

## 2. Architecture

```
                    ┌─────────────────────────────────┐
                    │        TikTok Video URL         │
                    └────────────────┬────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        Local TikTok MCP                         ScrapeCreator MCP
       (yt-dlp metadata)                        (Reference Adapter)
                 │                                       │
                 ▼                                       ▼
         Local Normalized                       Reference Normalized
            Data Model                               Data Model
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                           QA / Comparison Engine
                               (QAComparator)
                                     │
                                     ▼
                            Metrics Calculation
                           (QAMetricsCalculator)
                                     │
                                     ▼
                         Human-Readable QA Report &
                           Raw JSON Test Artifact
```

### Directory Structure

```
ContentScrapper/
├── server.py                   # FastMCP server entrypoint (stdio transport)
├── requirements.txt            # Python dependencies (mcp, yt-dlp, pydantic, pytest)
├── README.md                   # Documentation and usage guide
├── .gitignore                  # Git ignore rules
│
├── scrapers/                   # Scraper extraction layer
│   ├── __init__.py
│   ├── base.py                 # BaseScraper abstract interface
│   └── tiktok.py               # TikTokScraper implementation (yt-dlp + VTT parser)
│
├── qa/                         # Comparative QA and benchmarking layer
│   ├── __init__.py
│   ├── comparator.py           # Deep field-by-field comparator (static & dynamic tolerances)
│   ├── metrics.py              # Quality score and rate calculation
│   ├── reporter.py             # Human-readable report generator & JSON artifact writer
│   ├── runner.py               # Orchestrator for comparative benchmarking
│   ├── scrapecreator_adapter.py # Adapter & fixture cache for ScrapeCreator MCP
│   ├── cache/                  # Reference fixtures from ScrapeCreator
│   └── results/                # Timestamped raw benchmark results
│
├── tests/                      # Verification test suites
│   ├── test_tiktok.py          # Level 1 Unit tests (URL, VTT parsing, comparator, metrics)
│   ├── verify_mcp.py           # Level 3 MCP server tool discovery and execution
│   ├── benchmark_tiktok.py     # Level 4 CLI Comparative QA benchmark runner
│   └── urls.txt                # Configurable test case dataset
│
└── utils/                      # Helper utilities
    ├── __init__.py
    └── logging.py              # Stderr-only logger for MCP stdio protocol safety
```

---

## 3. Local Scraper Design & Stdout Safety

- **Zero Physical Media Download**: All video scraping uses `yt-dlp` in metadata mode (`skip_download=True`). Direct stream URLs and audio stream URLs are captured without saving video files to disk.
- **Stdio Protocol Safety**: Standard MCP communication relies on `stdin`/`stdout`. Any unformatted `print()` statements corrupt JSON-RPC messaging. All internal loggers, including `yt-dlp` logs, are redirected strictly to `sys.stderr`.
- **Native Subtitle & Transcript Extraction**: Captures `subtitles` and `automatic_captions` WEBVTT streams from TikTok CDN, parses them into structured `{start, end, text}` segments, and produces clean full text.

---

## 4. ScrapeCreator Benchmark Reference

In this environment, ScrapeCreator MCP serves as the reference benchmark:
- **Video Tool**: `mcp__scrape-creators__v2_tiktok_video`
- **Transcript Tool**: `mcp__scrape-creators__v1_tiktok_video_transcript`
- **Adapter**: `qa/scrapecreator_adapter.py` normalizes raw ScrapeCreator responses into the common schema and caches fixtures under `qa/cache/`.

---

## 5. Quick Start (1-Click Automated Setup)

Cukup jalankan satu perintah berikut di Command Prompt (CMD), PowerShell, atau Terminal. Script akan otomatis membuat virtual environment, menginstal dependensi (`yt-dlp`, `playwright`, `mcp`), mengunduh headless browser, dan mendaftarkan server langsung ke config Claude Desktop Anda:

### Windows (Command Prompt / CMD)
```cmd
git clone https://github.com/hasanzain/ContentScrapper.git && cd ContentScrapper && install.bat
```

### Windows (PowerShell)
```powershell
git clone https://github.com/hasanzain/ContentScrapper.git; cd ContentScrapper; .\install.ps1
```

### macOS / Linux / Manual Python
```bash
git clone https://github.com/hasanzain/ContentScrapper.git
cd ContentScrapper
python install.py
```

Setelah selesai, cukup **Restart Claude Desktop**. Tool `scrape_tiktok_video`, `get_tiktok_transcript`, `search_tiktok_videos`, dan `search_tiktok_mobile` langsung aktif dan siap digunakan.

---

### Manual Setup (Opsional)
Jika Anda ingin menyiapkan manual langkah demi langkah:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium-headless-shell
```

---

## 6. Available MCP Tools

The FastMCP server exposes three tools:

### `search_tiktok_videos`
- **Parameters**: `query` (str), `count` (int, default: 10)
- **Description**: Searches TikTok for viral videos matching a keyword or phrase without API credits using local browser automation.
- **Output Schema**:
```json
{
  "success": true,
  "platform": "tiktok",
  "query": "resep viral",
  "count": 5,
  "videos": [
    {
      "id": "7693833915370556692",
      "url": "https://www.tiktok.com/@ngadonwithlegi_/video/7693833915370556692",
      "author": "ngadonwithlegi",
      "description": "Resep makanan yg lagi viral Chocolate Tangyuan!",
      "thumbnail_url": "https://p16-common-sign.tiktokcdn.com/..."
    }
  ]
}
```

### `scrape_tiktok_video`
- **Parameters**: `url` (str)
- **Output Schema**:
```json
{
  "success": true,
  "platform": "tiktok",
  "url": "https://www.tiktok.com/@user/video/123",
  "id": "123",
  "description": "Video caption text",
  "creator": {
    "username": "user",
    "display_name": "User Display Name",
    "id": "12345678",
    "avatar_url": null
  },
  "statistics": {
    "views": 239000,
    "likes": 21200,
    "comments": 735,
    "shares": 433,
    "downloads": 0,
    "favorites": 1899
  },
  "video": {
    "duration": 8,
    "width": 1080,
    "height": 1920,
    "thumbnail_url": "https://p16-sign.tiktokcdn.com/...",
    "direct_url": "https://v16-webapp.tiktok.com/...",
    "formats": [
      {
        "format_id": "download",
        "url": "https://...",
        "ext": "mp4",
        "width": 1080,
        "height": 1920,
        "vcodec": "h264",
        "acodec": "aac"
      }
    ]
  },
  "sound": {
    "title": "original sound",
    "author": "Creator",
    "id": null,
    "url": null
  },
  "timestamp": "1793506316",
  "raw": {}
}
```

### `get_tiktok_transcript`
- **Parameters**: `url` (str)
- **Output Schema**:
```json
{
  "success": true,
  "platform": "tiktok",
  "url": "https://www.tiktok.com/@user/video/123",
  "available": true,
  "language": "eng-US",
  "segments": [
    {
      "start": 0.02,
      "end": 2.48,
      "text": "Welcome to New York City!"
    }
  ],
  "text": "Welcome to New York City!"
}
```

---

## 7. Claude Desktop MCP Configuration

Add the local server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tiktok-scraper": {
      "command": "F:\\Hasan\\SANDBOX\\ContentScrapper\\venv\\Scripts\\python.exe",
      "args": [
        "F:\\Hasan\\SANDBOX\\ContentScrapper\\server.py"
      ]
    }
  }
}
```

> **Note**: Do not modify or remove existing configurations such as `scrape-creators`.

---

## 8. Running Tests & Benchmarks

### Level 1: Unit Tests (No Internet Required)
```powershell
.\venv\Scripts\python.exe -m pytest tests/test_tiktok.py -v
```

### Level 3: MCP Tool Discovery & Verification
```powershell
.\venv\Scripts\python.exe tests/verify_mcp.py
```

### Level 4: Comparative QA Benchmark
Run benchmark across all URLs listed in `tests/urls.txt`:
```powershell
.\venv\Scripts\python.exe tests/benchmark_tiktok.py
```

Or benchmark a specific URL directly:
```powershell
.\venv\Scripts\python.exe tests/benchmark_tiktok.py "https://www.tiktok.com/@ophia.roserose/video/7703050842051579158"
```

Raw benchmark results are saved to `qa/results/<timestamp>-<video_id>.json`.

---

## 9. QA Scoring & Metrics

Fields are categorized into:
- **STATIC**: `video.id`, `creator.username`, `creator.id`, `video.duration`, `video.description`, `sound.id`, `sound.title`, `video.thumbnail_url`, `video.direct_url`, `transcript.text`
- **DYNAMIC**: `statistics.views`, `statistics.likes`, `statistics.comments`, `statistics.shares`, `statistics.favorites`, `statistics.downloads` (evaluated with dynamic tolerance variance threshold).

### Classifications
- `MATCH`: Exact equivalence.
- `APPROXIMATE_MATCH`: Dynamic numbers within tolerance or proportional dimensions.
- `MISMATCH`: Comparable values differing beyond tolerance.
- `LOCAL_ONLY`: Field captured by local scraper but absent in reference.
- `REFERENCE_ONLY`: Field captured by reference but absent in local.
- `BOTH_MISSING`: Absent in both.

### Overall Score Formula
```
Overall Score = 
    40% × Metadata Accuracy
  + 25% × Statistics Coverage
  + 15% × Creator Coverage
  + 10% × Media Coverage
  + 10% × Transcript Coverage
```

### Recommendations
- **PASS**: Overall Score ≥ 80% with no critical mismatches (`video.id`, `creator.username`).
- **NEED IMPROVEMENT**: Overall Score 50% – 79.9%.
- **FAIL**: Overall Score < 50% or critical field mismatch.

---

## 10. Comparative Findings: Local vs ScrapeCreator

| Capability | Local TikTok MCP | ScrapeCreator MCP | Note |
| :--- | :--- | :--- | :--- |
| **Cost / Credits** | **100% Free** | Consumes paid credits | Local has zero runtime costs |
| **Video ID & Username** | Exact Match (100%) | Exact Match (100%) | Full parity |
| **Direct Video Streams** | **14 streams (Full HD 1080p, 720p, audio)** | 1 preview stream | **Local advantage** |
| **Subtitles / Transcript** | Full VTT + Timestamps | Full VTT + Timestamps | 100% segment parity |
| **Statistics (Views/Likes)** | Real-time extraction | Real-time extraction | < 2% drift |
| **Creator Avatar** | Null | Available | Reference advantage |
| **Sound Music ID** | Null | Available | Reference advantage |
| **Download Count** | 0 (Hidden by web UI) | Available (internal API) | Reference advantage |

---

## 11. Known Limitations, Mobile API Issues & Troubleshooting Guide

### 11.1 General Web Limitations
1. **Avatar & Sound ID**: `yt-dlp` extracts web-page metadata where creator avatar and internal music IDs are not parsed by default into top-level fields.
2. **Download Count**: TikTok web interface does not display video download count; it is only available via authenticated app APIs.

### 11.2 Mobile App API Known Issues & Edge Blocks (`search_tiktok_mobile`)
`search_tiktok_mobile` meniru Android Client (`com.zhiliaoapp.musically`) dengan signature `X-Gorgon` / `X-Khronos` (v04.04).

#### Gejala Masalah (Symptoms)
- **HTTP 200 dengan payload 0 byte (`Content-Length: 0`)**:
  - **Penyebab**: Akamai WAF Edge memblokir koneksi TLS fingerprint Python (`httpx`/OpenSSL). Client asli TikTok memakai Google Cronet / TTNet stack (`TTNetVersion:a6c8e312`) dengan JA3/JA4 fingerprint spesifik.
  - **Dampak**: Request tidak sampai ke upstream backend TikTok; dihentikan langsung di Akamai edge.
- **HTTP 403 / Captcha challenge**:
  - **Penyebab**: Hash `X-Gorgon` / `X-Khronos` tidak sinkron dengan `X-SS-REQ-TICKET` atau request butuh signature generasi baru (`X-Argus`, `X-Ladon`).
- **Device ID Stale**:
  - **Penyebab**: `device_id`, `iid`, dan `openudid` statis di-flag oleh anti-abuse TikTok jika dipanggil repetitif dari IP sama tanpa proxy rotation.

#### Troubleshooting & Solusi untuk AI / Developer
1. **Fallback Utama**: Gunakan `search_tiktok_videos` (Playwright headless Chromium dengan session warmup di `/explore`). Tool ini 100% andal menembus bot-guard web tanpa masalah signature mobile.
2. **Jika ingin mengaktifkan Mobile API murni**:
   - Pasang library TLS spoofing (seperti `curl_cffi` dengan impersonasi `chrome` atau Android Cronet).
   - Implementasikan signature generator `X-Argus` / `X-Ladon` (memerlukan unpacking native binary `libbytebench.so` atau service remote signing).
   - Siapkan pool rotasi device ID dan residential proxy Indonesia.

---

## 12. Extensibility (Instagram / YouTube / X)
The `scrapers/base.py` `BaseScraper` interface allows adding:
- `scrapers/instagram.py` (`InstagramScraper`)
- `scrapers/youtube.py` (`YouTubeScraper`)
- `scrapers/twitter.py` (`TwitterScraper`)
Each plugs directly into `server.py` and the existing `qa/comparator.py` engine without architectural changes.
