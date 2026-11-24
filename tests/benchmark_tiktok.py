import argparse
import io
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qa.runner import QARunner
from utils.logging import get_logger

logger = get_logger("benchmark_cli")


def load_urls(urls_file: Path) -> list[str]:
    urls = []
    if urls_file.exists():
        with open(urls_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    urls.append(stripped)
    return urls


def main():
    parser = argparse.ArgumentParser(
        description="Run Comparative QA benchmark between Local Scraper and ScrapeCreator reference."
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more TikTok video URLs to benchmark. If omitted, tests/urls.txt is used.",
    )
    parser.add_argument(
        "--urls-file",
        default=str(Path(__file__).parent / "urls.txt"),
        help="Path to file containing URLs (default: tests/urls.txt)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save raw JSON results to qa/results/",
    )

    args = parser.parse_args()

    urls_to_test = args.urls
    if not urls_to_test:
        urls_to_test = load_urls(Path(args.urls_file))

    if not urls_to_test:
        print("[ERROR] No URLs provided and tests/urls.txt is empty.")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"STARTING TIKTOK SCRAPER COMPARATIVE QA BENCHMARK")
    print(f"Total test cases: {len(urls_to_test)}")
    print(f"{'='*70}\n")

    runner = QARunner()
    summaries = []

    for idx, url in enumerate(urls_to_test, start=1):
        print(f"\n>>> Running Benchmark Case #{idx}: {url}")
        res = runner.run_benchmark(
            url=url,
            save_artifact=not args.no_save,
        )

        print("\n" + res["report"])
        if res.get("artifact_path"):
            print(f"Artifact saved: {res['artifact_path']}")

        metrics = res["metrics"]
        summaries.append({
            "idx": idx,
            "url": url,
            "score": metrics["overall_score"],
            "coverage": metrics["coverage_percent"],
            "exact": metrics["exact_match_rate"],
            "approx": metrics["approx_match_rate"],
            "mismatch": metrics["mismatch_rate"],
            "rec": metrics["recommendation"],
        })

    # Summary Table
    print("\n" + "=" * 70)
    print("BENCHMARK AGGREGATED SUMMARY")
    print("=" * 70)
    print(f"{'#':<3} {'Score':<8} {'Coverage':<10} {'Exact':<8} {'Approx':<8} {'Mismatch':<10} {'Verdict':<12}")
    print("-" * 70)
    for s in summaries:
        print(
            f"{s['idx']:<3} {s['score']:<8} {s['coverage']:<10}% {s['exact']:<8}% "
            f"{s['approx']:<8}% {s['mismatch']:<10}% {s['rec']:<12}"
        )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
