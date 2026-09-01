from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .database import connect_database, initialize_database
from .publication import (
    JSON_COLUMN_NAMES,
    MAX_PUBLICATION_BYTES,
    load_validated_publication,
    validate_publication_frame,
)


def _sort_notices(frame: pd.DataFrame) -> pd.DataFrame:
    if "lifecycle_status" not in frame.columns:
        frame = frame.copy()
        frame["lifecycle_status"] = "unchanged"
    if "opportunity_score" in frame.columns:
        return frame.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    return frame.reset_index(drop=True)


def _load_sqlite(path: Path) -> pd.DataFrame:
    with connect_database(path) as connection:
        initialize_database(connection)
        frame = pd.read_sql_query("SELECT * FROM tender_notices", connection)
    return _sort_notices(frame)


def _load_json(path: Path) -> pd.DataFrame:
    payload = load_validated_publication(path)
    rows = []
    for notice in payload.get("notices", []):
        row = dict(notice)
        for database_name, public_name in JSON_COLUMN_NAMES.items():
            row[database_name] = json.dumps(
                row.pop(public_name, [] if public_name in {"cpv_codes", "place_codes"} else {}),
                ensure_ascii=False,
            )
        row.setdefault("raw_notice_json", "{}")
        rows.append(row)
    return _sort_notices(pd.DataFrame(rows))


def load_dashboard_data(
    *,
    database_path: Path,
    parquet_path: Path,
    json_path: Path,
) -> tuple[pd.DataFrame, str]:
    """Load dashboard records from the best locally available publication."""
    if database_path.exists():
        sqlite_frame = _load_sqlite(database_path)
        if not sqlite_frame.empty:
            return sqlite_frame, "Local SQLite"
    if parquet_path.exists():
        if parquet_path.stat().st_size > MAX_PUBLICATION_BYTES:
            raise ValueError("Parquet publication exceeds the configured size limit.")
        frame = pd.read_parquet(parquet_path)
        validate_publication_frame(frame)
        return _sort_notices(frame), "Published Parquet"
    if json_path.exists():
        return _load_json(json_path), "Published JSON"
    raise FileNotFoundError(
        "No SQLite database or published TED snapshot is available."
    )
