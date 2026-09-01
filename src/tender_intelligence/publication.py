from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .database import NOTICE_COLUMNS, read_notice_records, upsert_notices


SCHEMA_VERSION = "1.0"
JSON_COLUMN_NAMES = {
    "cpv_codes_json": "cpv_codes",
    "place_codes_json": "place_codes",
    "matched_keywords_json": "matched_keywords",
    "matched_cpv_json": "matched_cpv",
    "score_explanation_json": "score_explanation",
}
PUBLIC_DATABASE_COLUMNS = [
    column for column in NOTICE_COLUMNS if column != "raw_notice_json"
]


def _json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _public_record(row: dict[str, Any]) -> dict[str, Any]:
    record = {
        key: value for key, value in row.items()
        if key not in {*JSON_COLUMN_NAMES, "raw_notice_json"}
    }
    for database_name, public_name in JSON_COLUMN_NAMES.items():
        fallback: Any = [] if public_name in {"cpv_codes", "place_codes"} else {}
        record[public_name] = _json_value(row.get(database_name), fallback)
    return record


def export_publication(
    connection: sqlite3.Connection,
    output_dir: Path,
    *,
    metadata: dict[str, Any],
) -> dict[str, Path]:
    """Write a readable JSON publication and an analysis-ready Parquet file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_notice_records(connection)
    public_records = [_public_record(row) for row in rows]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {**metadata, "notice_count": len(public_records)},
        "notices": public_records,
    }

    json_path = output_dir / "tenders.json"
    json_temp = output_dir / ".tenders.json.tmp"
    json_temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    json_temp.replace(json_path)

    parquet_path = output_dir / "tenders.parquet"
    parquet_temp = output_dir / ".tenders.parquet.tmp"
    parquet_rows = [
        {column: row.get(column) for column in PUBLIC_DATABASE_COLUMNS}
        for row in rows
    ]
    frame = pd.DataFrame(parquet_rows, columns=PUBLIC_DATABASE_COLUMNS)
    frame.to_parquet(parquet_temp, index=False, engine="pyarrow", compression="snappy")
    parquet_temp.replace(parquet_path)
    return {"json": json_path, "parquet": parquet_path}


def restore_publication(
    connection: sqlite3.Connection, publication_path: Path
) -> int:
    """Restore persisted lifecycle state into an empty SQLite database."""
    if not publication_path.exists():
        return 0
    payload = json.loads(publication_path.read_text(encoding="utf-8"))
    records = []
    for notice in payload.get("notices", []):
        record = dict(notice)
        record.setdefault("cpv_codes", [])
        record.setdefault("place_codes", [])
        record.setdefault("matched_keywords", {})
        record.setdefault("matched_cpv", {})
        record.setdefault("score_explanation", {})
        record["raw_notice"] = {}
        records.append(record)
    return upsert_notices(connection, records)
