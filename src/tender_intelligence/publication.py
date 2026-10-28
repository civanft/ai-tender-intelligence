from __future__ import annotations

import json
import gzip
import hmac
import math
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from .database import (
    read_notice_records,
    record_content_hash,
    upsert_notices,
)
from .normalize import is_valid_notice_id, trusted_ted_url


SCHEMA_VERSION = "1.0"
MAX_PUBLICATION_BYTES = 95 * 1024 * 1024
MAX_PUBLICATION_NOTICES = 100_000
MAX_DECOMPRESSED_PUBLICATION_BYTES = 256 * 1024 * 1024
MAX_PLAIN_JSON_BYTES = 90 * 1024 * 1024
JSON_COLUMN_NAMES = {
    "cpv_codes_json": "cpv_codes",
    "place_codes_json": "place_codes",
    "matched_keywords_json": "matched_keywords",
    "matched_cpv_json": "matched_cpv",
    "score_explanation_json": "score_explanation",
}
# This is deliberately independent from NOTICE_COLUMNS. New internal database
# columns must never become public merely because the storage schema grows.
PUBLIC_DATABASE_COLUMNS = [
    "notice_id",
    "publication_date",
    "title",
    "buyer_name",
    "buyer_country",
    "sector",
    "cpv_codes_json",
    "place_codes_json",
    "estimated_value",
    "currency",
    "deadline_date",
    "notice_type",
    "procedure_type",
    "ted_url",
    "description",
    "primary_theme",
    "matched_keywords_json",
    "matched_cpv_json",
    "classification_score",
    "is_relevant",
    "opportunity_score",
    "score_explanation_json",
    "fetched_at",
    "first_seen_at",
    "last_seen_at",
    "lifecycle_status",
    "content_hash",
    "closed_at",
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
PUBLIC_METADATA_FIELDS = {
    "generated_at",
    "source",
    "query",
    "countries",
    "scope",
    "api_match_count",
    "received_count",
    "fetched_page_count",
    "is_complete",
    "lifecycle",
    "notice_count",
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
        key: row.get(key) for key in PUBLIC_DATABASE_COLUMNS
        if key not in JSON_COLUMN_NAMES
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o644)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def resolve_publication_json(path: Path) -> Path:
    """Retain support for small/legacy JSON and large gzip publications."""
    compressed = path.with_suffix(path.suffix + ".gz")
    return path if path.exists() or path.suffix == ".gz" else compressed


def load_validated_publication(path: Path) -> dict[str, Any]:
    """Load a bounded, internally consistent publication snapshot."""
    path = resolve_publication_json(path)
    if path.stat().st_size > MAX_PUBLICATION_BYTES:
        raise ValueError("Publication exceeds the configured size limit.")
    try:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rb") as handle:
            raw = handle.read(MAX_DECOMPRESSED_PUBLICATION_BYTES + 1)
        if len(raw) > MAX_DECOMPRESSED_PUBLICATION_BYTES:
            raise ValueError("Decompressed publication exceeds the configured size limit.")
        payload = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_nonstandard_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, gzip.BadGzipFile, EOFError) as exc:
        raise ValueError("Publication is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Publication schema version is unsupported.")
    metadata = payload.get("metadata")
    notices = payload.get("notices")
    if not isinstance(metadata, dict) or not isinstance(notices, list):
        raise ValueError("Publication metadata or notices collection is invalid.")
    if set(metadata) - PUBLIC_METADATA_FIELDS:
        raise ValueError("Publication metadata contains non-public fields.")
    if len(notices) > MAX_PUBLICATION_NOTICES:
        raise ValueError("Publication contains too many notices.")
    if metadata.get("notice_count") != len(notices):
        raise ValueError("Publication notice count does not match its metadata.")

    seen_ids: set[str] = set()
    for notice in notices:
        if not isinstance(notice, dict) or set(notice) != PUBLIC_JSON_COLUMNS:
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
    if (
        missing
        or set(frame.columns) - set(PUBLIC_DATABASE_COLUMNS)
        or len(frame) > MAX_PUBLICATION_NOTICES
    ):
        raise ValueError("Parquet publication schema or row count is invalid.")
    if frame["notice_id"].isna().any() or frame["notice_id"].duplicated().any():
        raise ValueError("Parquet publication notice identifiers are invalid.")
    if not frame["notice_id"].map(is_valid_notice_id).all():
        raise ValueError("Parquet publication notice identifiers are invalid.")
    if not set(frame["lifecycle_status"].dropna()).issubset(LIFECYCLE_STATUSES):
        raise ValueError("Parquet publication contains an invalid lifecycle status.")
    # The usual TED fallback is deterministic once the notice ID is validated.
    # Compare that common case in bulk; retain the full URL parser for any
    # supplied link that differs from the canonical fallback.
    canonical_urls = "https://ted.europa.eu/en/notice/-/detail/" + frame["notice_id"]
    noncanonical = frame["ted_url"].ne(canonical_urls).fillna(True)
    for notice_id, candidate in frame.loc[noncanonical, ["notice_id", "ted_url"]].itertuples(
        index=False, name=None
    ):
        if not isinstance(candidate, str) or candidate != trusted_ted_url(candidate, notice_id):
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
    if set(metadata) - PUBLIC_METADATA_FIELDS:
        raise ValueError("Publication metadata contains non-public fields.")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_notice_records(connection)
    public_records = [_public_record(row) for row in rows]
    if len(public_records) > MAX_PUBLICATION_NOTICES:
        raise ValueError("Publication contains too many notices.")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {**metadata, "notice_count": len(public_records)},
        "notices": public_records,
    }

    raw_json = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(raw_json) > MAX_DECOMPRESSED_PUBLICATION_BYTES:
        raise ValueError("Publication exceeds the bounded decompressed size limit.")
    compressed_json = gzip.compress(raw_json, mtime=0)
    if len(compressed_json) > MAX_PUBLICATION_BYTES:
        raise ValueError("Compressed publication exceeds the configured size limit.")
    plain_json_path = output_dir / "tenders.json"
    compressed_json_path = output_dir / "tenders.json.gz"
    json_path = plain_json_path if len(raw_json) <= MAX_PLAIN_JSON_BYTES else compressed_json_path

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
        if temporary_path.stat().st_size > MAX_PUBLICATION_BYTES:
            raise ValueError("Parquet publication exceeds the configured size limit.")
        temporary_path.chmod(0o644)
        _atomic_write_bytes(compressed_json_path, compressed_json)
        if json_path == plain_json_path:
            _atomic_write_bytes(plain_json_path, raw_json)
        else:
            # Superseded generated output only; never leave a stale plain JSON fallback.
            plain_json_path.unlink(missing_ok=True)
        temporary_path.replace(parquet_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {"json": json_path, "parquet": parquet_path}


def restore_publication(
    connection: sqlite3.Connection, publication_path: Path
) -> int:
    """Restore persisted lifecycle state into an empty SQLite database."""
    publication_path = resolve_publication_json(publication_path)
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
