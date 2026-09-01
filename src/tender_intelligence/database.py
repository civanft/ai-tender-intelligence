from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .normalize import trusted_ted_url
from .paths import DEFAULT_DB_PATH, SCHEMA_PATH


NOTICE_COLUMNS = [
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
    "raw_notice_json",
    "fetched_at",
    "first_seen_at",
    "last_seen_at",
    "lifecycle_status",
    "content_hash",
    "closed_at",
]

CONTENT_HASH_COLUMNS = [
    column for column in NOTICE_COLUMNS
    if column not in {
        "raw_notice_json", "fetched_at", "first_seen_at", "last_seen_at",
        "lifecycle_status", "content_hash", "closed_at",
    }
]
HASH_JSON_COLUMNS = {
    "cpv_codes_json",
    "place_codes_json",
    "matched_keywords_json",
    "matched_cpv_json",
    "score_explanation_json",
}

LIFECYCLE_MIGRATIONS = {
    "first_seen_at": "TEXT NOT NULL DEFAULT ''",
    "last_seen_at": "TEXT NOT NULL DEFAULT ''",
    "lifecycle_status": "TEXT NOT NULL DEFAULT 'new'",
    "content_hash": "TEXT NOT NULL DEFAULT ''",
    "closed_at": "TEXT",
}

FETCH_RUN_MIGRATIONS = {
    "fetched_page_count": "INTEGER NOT NULL DEFAULT 0",
    "is_complete": "INTEGER NOT NULL DEFAULT 0",
    "new_count": "INTEGER NOT NULL DEFAULT 0",
    "updated_count": "INTEGER NOT NULL DEFAULT 0",
    "unchanged_count": "INTEGER NOT NULL DEFAULT 0",
    "closed_count": "INTEGER NOT NULL DEFAULT 0",
    "publication_json_path": "TEXT",
    "publication_parquet_path": "TEXT",
}

NOTICE_UPSERT_SQL = """
INSERT INTO tender_notices (
    notice_id, publication_date, title, buyer_name, buyer_country, sector,
    cpv_codes_json, place_codes_json, estimated_value, currency, deadline_date,
    notice_type, procedure_type, ted_url, description, primary_theme,
    matched_keywords_json, matched_cpv_json, classification_score, is_relevant,
    opportunity_score, score_explanation_json, raw_notice_json, fetched_at,
    first_seen_at, last_seen_at, lifecycle_status, content_hash, closed_at
) VALUES (
    :notice_id, :publication_date, :title, :buyer_name, :buyer_country, :sector,
    :cpv_codes_json, :place_codes_json, :estimated_value, :currency, :deadline_date,
    :notice_type, :procedure_type, :ted_url, :description, :primary_theme,
    :matched_keywords_json, :matched_cpv_json, :classification_score, :is_relevant,
    :opportunity_score, :score_explanation_json, :raw_notice_json, :fetched_at,
    :first_seen_at, :last_seen_at, :lifecycle_status, :content_hash, :closed_at
) ON CONFLICT(notice_id) DO UPDATE SET
    publication_date=excluded.publication_date,
    title=excluded.title,
    buyer_name=excluded.buyer_name,
    buyer_country=excluded.buyer_country,
    sector=excluded.sector,
    cpv_codes_json=excluded.cpv_codes_json,
    place_codes_json=excluded.place_codes_json,
    estimated_value=excluded.estimated_value,
    currency=excluded.currency,
    deadline_date=excluded.deadline_date,
    notice_type=excluded.notice_type,
    procedure_type=excluded.procedure_type,
    ted_url=excluded.ted_url,
    description=excluded.description,
    primary_theme=excluded.primary_theme,
    matched_keywords_json=excluded.matched_keywords_json,
    matched_cpv_json=excluded.matched_cpv_json,
    classification_score=excluded.classification_score,
    is_relevant=excluded.is_relevant,
    opportunity_score=excluded.opportunity_score,
    score_explanation_json=excluded.score_explanation_json,
    raw_notice_json=excluded.raw_notice_json,
    fetched_at=excluded.fetched_at,
    first_seen_at=excluded.first_seen_at,
    last_seen_at=excluded.last_seen_at,
    lifecycle_status=excluded.lifecycle_status,
    content_hash=excluded.content_hash,
    closed_at=excluded.closed_at
"""

FETCH_RUN_INSERT_SQL = """
INSERT INTO fetch_runs (
    query, countries, scope, requested_limit, api_match_count, received_count,
    relevant_count, started_at, completed_at, status, error_message,
    raw_snapshot_path, fetched_page_count, is_complete, new_count, updated_count,
    unchanged_count, closed_count, publication_json_path, publication_parquet_path
) VALUES (
    :query, :countries, :scope, :requested_limit, :api_match_count, :received_count,
    :relevant_count, :started_at, :completed_at, :status, :error_message,
    :raw_snapshot_path, :fetched_page_count, :is_complete, :new_count, :updated_count,
    :unchanged_count, :closed_count, :publication_json_path, :publication_parquet_path
)
"""


def connect_database(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(path)
    if os.name == "posix":
        path.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(tender_notices)")
    }
    lifecycle_was_missing = "lifecycle_status" not in existing_columns
    for column, declaration in LIFECYCLE_MIGRATIONS.items():
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE tender_notices ADD COLUMN {column} {declaration}"
            )
    connection.execute(
        "UPDATE tender_notices SET first_seen_at=fetched_at WHERE first_seen_at=''"
    )
    connection.execute(
        "UPDATE tender_notices SET last_seen_at=fetched_at WHERE last_seen_at=''"
    )
    if lifecycle_was_missing:
        connection.execute(
            "UPDATE tender_notices SET lifecycle_status='unchanged'"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_tenders_lifecycle "
        "ON tender_notices (lifecycle_status)"
    )
    fetch_run_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(fetch_runs)")
    }
    for column, declaration in FETCH_RUN_MIGRATIONS.items():
        if column not in fetch_run_columns:
            connection.execute(
                f"ALTER TABLE fetch_runs ADD COLUMN {column} {declaration}"
            )
    connection.commit()


def _database_row(record: dict[str, Any]) -> dict[str, Any]:
    fetched_at = record["fetched_at"]
    row = {
        "notice_id": record["notice_id"],
        "publication_date": record.get("publication_date"),
        "title": record["title"],
        "buyer_name": record.get("buyer_name"),
        "buyer_country": record.get("buyer_country"),
        "sector": record.get("sector"),
        "cpv_codes_json": json.dumps(record.get("cpv_codes", []), ensure_ascii=False),
        "place_codes_json": json.dumps(record.get("place_codes", []), ensure_ascii=False),
        "estimated_value": (
            float(record["estimated_value"])
            if record.get("estimated_value") is not None else None
        ),
        "currency": record.get("currency"),
        "deadline_date": record.get("deadline_date"),
        "notice_type": record.get("notice_type"),
        "procedure_type": record.get("procedure_type"),
        "ted_url": trusted_ted_url(record.get("ted_url"), str(record["notice_id"])),
        "description": record.get("description"),
        "primary_theme": record["primary_theme"],
        "matched_keywords_json": json.dumps(
            record.get("matched_keywords", {}), ensure_ascii=False
        ),
        "matched_cpv_json": json.dumps(record.get("matched_cpv", {}), ensure_ascii=False),
        "classification_score": float(record["classification_score"]),
        "is_relevant": int(record["is_relevant"]),
        "opportunity_score": float(record["opportunity_score"]),
        "score_explanation_json": json.dumps(
            record["score_explanation"], ensure_ascii=False
        ),
        "raw_notice_json": json.dumps(record["raw_notice"], ensure_ascii=False),
        "fetched_at": fetched_at,
        "first_seen_at": record.get("first_seen_at") or fetched_at,
        "last_seen_at": record.get("last_seen_at") or fetched_at,
        "lifecycle_status": record.get("lifecycle_status") or "new",
        "content_hash": record.get("content_hash") or "",
        "closed_at": record.get("closed_at"),
    }
    if not row["content_hash"]:
        payload = {}
        for column in CONTENT_HASH_COLUMNS:
            value = row[column]
            if column in HASH_JSON_COLUMNS and isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            payload[column] = value
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        row["content_hash"] = hashlib.sha256(encoded).hexdigest()
    return row


def record_content_hash(record: dict[str, Any]) -> str:
    """Recalculate a record hash without trusting a persisted hash value."""
    candidate = dict(record)
    candidate["content_hash"] = ""
    return str(_database_row(candidate)["content_hash"])


def _write_rows(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    connection.executemany(NOTICE_UPSERT_SQL, rows)
    connection.commit()
    return len(rows)


def upsert_notices(
    connection: sqlite3.Connection, records: Iterable[dict[str, Any]]
) -> int:
    rows = [_database_row(record) for record in records]
    return _write_rows(connection, rows)


def read_notice_records(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row) for row in connection.execute(
            "SELECT * FROM tender_notices ORDER BY notice_id"
        ).fetchall()
    ]


def sync_notices(
    connection: sqlite3.Connection,
    records: Iterable[dict[str, Any]],
    *,
    close_missing: bool,
    countries: Iterable[str] | None = None,
    observed_at: str | None = None,
) -> dict[str, int]:
    """Upsert a complete or partial observation and assign lifecycle states."""
    incoming = [_database_row(record) for record in records]
    existing = {
        row["notice_id"]: row
        for row in connection.execute(
            "SELECT notice_id, content_hash, first_seen_at, lifecycle_status "
            "FROM tender_notices"
        ).fetchall()
    }
    stats = {"new": 0, "updated": 0, "unchanged": 0, "closed": 0}
    for row in incoming:
        previous = existing.get(row["notice_id"])
        if previous is None:
            status = "new"
        elif (
            previous["content_hash"] != row["content_hash"]
            or previous["lifecycle_status"] == "closed"
        ):
            status = "updated"
        else:
            status = "unchanged"
        row["lifecycle_status"] = status
        row["first_seen_at"] = (
            previous["first_seen_at"] if previous and previous["first_seen_at"]
            else row["fetched_at"]
        )
        row["last_seen_at"] = row["fetched_at"]
        row["closed_at"] = None
        stats[status] += 1

    _write_rows(connection, incoming)

    if close_missing:
        seen_ids = {row["notice_id"] for row in incoming}
        target_countries = sorted(
            {str(country) for country in (countries or []) if str(country).strip()}
            or {str(row["buyer_country"]) for row in incoming if row["buyer_country"]}
        )
        closure_time = observed_at or (incoming[0]["fetched_at"] if incoming else None)
        if not closure_time:
            raise ValueError("observed_at is required to close missing notices without records.")
        if target_countries:
            candidates = connection.execute(
                "SELECT notice_id FROM tender_notices "
                "WHERE buyer_country IN (SELECT value FROM json_each(?)) "
                "AND lifecycle_status != 'closed'",
                (json.dumps(target_countries),),
            ).fetchall()
            missing_ids = [row["notice_id"] for row in candidates if row["notice_id"] not in seen_ids]
            if missing_ids:
                connection.execute(
                    "UPDATE tender_notices SET lifecycle_status='closed', closed_at=? "
                    "WHERE notice_id IN (SELECT value FROM json_each(?))",
                    (closure_time, json.dumps(missing_ids)),
                )
                connection.commit()
                stats["closed"] = len(missing_ids)
    return stats


def record_fetch_run(connection: sqlite3.Connection, run: dict[str, Any]) -> None:
    connection.execute(FETCH_RUN_INSERT_SQL, run)
    connection.commit()
