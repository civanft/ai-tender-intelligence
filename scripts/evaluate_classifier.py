#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tender_intelligence.evaluation import (  # noqa: E402
    evaluate_manual_labels,
    load_label_file,
    load_labeling_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate weighted and unweighted classifier metrics."
    )
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "data" / "evaluation" / "round_1_manifest.json",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def main() -> int:
    args = parse_args()
    try:
        manifest = load_labeling_manifest(args.manifest)
        labels = load_label_file(args.labels)
        report = evaluate_manual_labels(manifest, labels)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    coverage = report["coverage"]
    weighted = report["weighted"]
    print(f"Round: {report['round_id']} ({report['status']})")
    print(
        "Coverage: "
        f"{coverage['decided_count']}/{coverage['sample_count']} decided, "
        f"{coverage['unsure_count']} unsure, {coverage['blank_count']} blank"
    )
    print(f"Weighted precision: {_format_rate(weighted['precision'])}")
    print(f"Weighted recall: {_format_rate(weighted['recall'])}")
    print(f"Weighted F1: {_format_rate(weighted['f1'])}")
    print(report["scope_note"])

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.output.chmod(0o644)
        print(f"Report written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
