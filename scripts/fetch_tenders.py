#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tender_intelligence.pipeline import run_pipeline  # noqa: E402
from tender_intelligence.ted_client import TedApiError  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and classify AI/data tender candidates from EU TED."
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["BEL", "ITA", "FIN"],
        help="ISO alpha-3 buyer countries (default: BEL ITA FIN).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional total notice cap. Omit to retrieve every matching page.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=250,
        help="TED notices requested per page, from 1 to 250 (default: 250).",
    )
    parser.add_argument(
        "--scope",
        choices=["LATEST", "ACTIVE", "ALL"],
        default="ACTIVE",
        help="TED search scope (default: ACTIVE).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the generated query without fetching or writing notices.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        print("Error: --limit must be positive when provided.", file=sys.stderr)
        return 2
    if not 1 <= args.page_size <= 250:
        print("Error: --page-size must be between 1 and 250.", file=sys.stderr)
        return 2
    try:
        result = run_pipeline(
            countries=args.countries,
            limit=args.limit,
            page_size=args.page_size,
            scope=args.scope,
            dry_run=args.dry_run,
        )
    except (TedApiError, ValueError) as exc:
        print(f"Fetch failed: {exc}", file=sys.stderr)
        return 1

    if result["status"] == "validated":
        print("TED accepted the generated expert query.")
        print(result["query"])
        return 0

    print("TED pipeline completed successfully.")
    print(f"API matches: {result['api_match_count']}")
    print(f"Candidates received: {result['received_count']}")
    print(f"Pages fetched: {result['fetched_page_count']}")
    print(f"Complete ACTIVE snapshot: {result['is_complete']}")
    print(f"Locally relevant: {result['relevant_count']}")
    lifecycle = result["lifecycle"]
    print(
        "Lifecycle: "
        f"{lifecycle['new']} new, {lifecycle['updated']} updated, "
        f"{lifecycle['unchanged']} unchanged, {lifecycle['closed']} closed"
    )
    print(f"SQLite database: {result['database_path']}")
    print(f"Raw snapshot: {result['raw_snapshot_path']}")
    print(f"Published JSON: {result['publication_json_path']}")
    print(f"Published Parquet: {result['publication_parquet_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
