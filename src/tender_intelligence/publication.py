from __future__ import annotations

import json
import hmac
import math
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from .database import (
    NOTICE_COLUMNS,
    read_notice_records,
    record_content_hash,
    upsert_notices,
)
from .normalize import is_valid_notice_id, trusted_ted_url


SCHEMA_VERSION = "1.0"
MAX_PUBLICATION_BYTES = 95 * 1024 * 1024
MAX_PUBLICATION_NOTICES = 15_000
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
PUBLIC_JSON_COLUMNS = (
    set(PUBLIC_DATABASE_COLUMNS) - set(JSON_COLUMN_NAMES)
) | set(JSON_COLUMN_NAMES.values())
LIFECYCLE_STATUSES = {"new", "updated", "unchanged", "closed"}
FINITE_NUMERIC_COLUMNS = {
    "estimated_value",
    "classification_score",
    "opportunity_score",
}


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"Publication contains a non-standard numeric value: {value}.")


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


def _atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_validated_publication(path: Path) -> dict[str, Any]:
    """Load a bounded, internally consistent publication snapshot."""
    if path.stat().st_size > MAX_PUBLICATION_BYTES:
        raise ValueError("Publication exceeds the configured size limit.")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Publication is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Publication schema version is unsupported.")
    metadata = payload.get("metadata")
    notices = payload.get("notices")
    if not isinstance(metadata, dict) or not isinstance(notices, list):
        raise ValueError("Publication metadata or notices collection is invalid.")
    if len(notices) > MAX_PUBLICATION_NOTICES:
        raise ValueError("Publication contains too many notices.")
    if metadata.get("notice_count") != len(notices):
        raise ValueError("Publication notice count does not match its metadata.")

    seen_ids: set[str] = set()
    for notice in notices:
        if not isinstance(notice, dict) or not PUBLIC_JSON_COLUMNS.issubset(notice):
            raise ValueError("Publication notice schema is incomplete.")
        notice_id = notice.get("notice_id")
        if not is_valid_notice_id(notice_id) or notice_id in seen_ids:
            raise ValueError("Publication notice identifiers are invalid or duplicated.")
        seen_ids.add(notice_id)
        if notice.get("lifecycle_status") not in LIFECYCLE_STATUSES:
            raise ValueError("Publication contains an invalid lifecycle status.")
        if notice.get("ted_url") != trusted_ted_url(notice.get("ted_url"), notice_id):
            raise ValueError("Publication contains an untrusted TED URL.")
        for column in FINITE_NUMERIC_COLUMNS:
            value = notice.get(column)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
            ):
                raise ValueError("Publication contains an invalid numeric value.")

        record = dict(notice)
        record.setdefault("cpv_codes", [])
        record.setdefault("place_codes", [])
        record.setdefault("matched_keywords", {})
        record.setdefault("matched_cpv", {})
        record.setdefault("score_explanation", {})
        record["raw_notice"] = {}
        expected_hash = record_content_hash(record)
        provided_hash = notice.get("content_hash")
        if not isinstance(provided_hash, str) or not hmac.compare_digest(
            provided_hash, expected_hash
        ):
            raise ValueError("Publication content hash validation failed.")
    return payload


def validate_publication_frame(frame: pd.DataFrame) -> None:
    """Validate the bounded Parquet contract before the dashboard uses it."""
    missing = set(PUBLIC_DATABASE_COLUMNS) - set(frame.columns)
    if missing or len(frame) > MAX_PUBLICATION_NOTICES:
        raise ValueError("Parquet publication schema or row count is invalid.")
    if frame["notice_id"].isna().any() or frame["notice_id"].duplicated().any():
        raise ValueError("Parquet publication notice identifiers are invalid.")
    if not frame["notice_id"].map(is_valid_notice_id).all():
        raise ValueError("Parquet publication notice identifiers are invalid.")
    if not set(frame["lifecycle_status"].dropna()).issubset(LIFECYCLE_STATUSES):
        raise ValueError("Parquet publication contains an invalid lifecycle status.")
    for notice_id, candidate in zip(frame["notice_id"], frame["ted_url"], strict=True):
        if candidate != trusted_ted_url(candidate, str(notice_id)):
            raise ValueError("Parquet publication contains an untrusted TED URL.")
    for column in FINITE_NUMERIC_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid = frame[column].notna() & ~numeric.map(math.isfinite)
        if invalid.any():
            raise ValueError("Parquet publication contains an invalid numeric value.")


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
    _atomic_write_text(
        json_path,
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n",
    )

    parquet_path = output_dir / "tenders.parquet"
    parquet_rows = [
        {column: row.get(column) for column in PUBLIC_DATABASE_COLUMNS}
        for row in rows
    ]
    frame = pd.DataFrame(parquet_rows, columns=PUBLIC_DATABASE_COLUMNS)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=".tenders.parquet.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        frame.to_parquet(
            temporary_path, index=False, engine="pyarrow", compression="snappy"
        )
        temporary_path.chmod(0o644)
        temporary_path.replace(parquet_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {"json": json_path, "parquet": parquet_path}


def restore_publication(
    connection: sqlite3.Connection, publication_path: Path
) -> int:
    """Restore persisted lifecycle state into an empty SQLite database."""
    if not publication_path.exists():
        return 0
    payload = load_validated_publication(publication_path)
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
