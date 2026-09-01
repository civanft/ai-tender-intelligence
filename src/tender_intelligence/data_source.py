from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from .database import initialize_database
from .publication import JSON_COLUMN_NAMES


def _sort_notices(frame: pd.DataFrame) -> pd.DataFrame:
    if "lifecycle_status" not in frame.columns:
        frame = frame.copy()
        frame["lifecycle_status"] = "unchanged"
    if "opportunity_score" in frame.columns:
        return frame.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    return frame.reset_index(drop=True)


def _load_sqlite(path: Path) -> pd.DataFrame:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        initialize_database(connection)
        frame = pd.read_sql_query("SELECT * FROM tender_notices", connection)
    return _sort_notices(frame)


def _load_json(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
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
        return _sort_notices(pd.read_parquet(parquet_path)), "Published Parquet"
    if json_path.exists():
        return _load_json(json_path), "Published JSON"
    raise FileNotFoundError(
        "No SQLite database or published TED snapshot is available."
    )
