#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tender_intelligence.config import load_taxonomy  # noqa: E402
from tender_intelligence.evaluation import build_labeling_manifest  # noqa: E402
from tender_intelligence.paths import PUBLISHED_PARQUET_PATH  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reproducible stratified manual-labeling sample."
    )
    parser.add_argument("--input", type=Path, default=PUBLISHED_PARQUET_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "evaluation" / "round_1_manifest.json",
    )
    parser.add_argument("--round-id", default="round-1")
    parser.add_argument("--sample-size", type=int, default=120)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        print(f"Input publication not found: {args.input}", file=sys.stderr)
        return 2
    if args.output.exists() and not args.overwrite:
        print("Output exists; pass --overwrite to replace it.", file=sys.stderr)
        return 2
    taxonomy = load_taxonomy()
    frame = pd.read_parquet(args.input)
    try:
        source_label = args.input.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        source_label = args.input.name
    try:
        manifest = build_labeling_manifest(
            frame,
            round_id=args.round_id,
            sample_size=args.sample_size,
            random_seed=args.seed,
            taxonomy_version=str(taxonomy["version"]),
            classification_threshold=float(taxonomy["classification_threshold"]),
            source_path=args.input,
            source_label=source_label,
        )
    except ValueError as exc:
        print(f"Sample creation failed: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output.chmod(0o644)
    print(f"Created {len(manifest['records'])} labeling records: {args.output}")
    for stratum in manifest["strata"]:
        print(
            f"{stratum['stratum']}: {stratum['sample_count']} sampled from "
            f"{stratum['population_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
