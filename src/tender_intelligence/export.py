from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


DEFAULT_EXPORT_COLUMNS = (
    "notice_id",
    "title",
    "buyer_name",
    "buyer_country",
    "primary_theme",
    "publication_date",
    "deadline_date",
    "estimated_value",
    "currency",
    "opportunity_score",
    "lifecycle_status",
    "ted_url",
)


def neutralize_spreadsheet_formula(value: object) -> object:
    """Prevent CSV cells supplied by TED from being interpreted as formulas."""
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(" \t\r\n")
    if candidate.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def export_notices_csv(
    frame: pd.DataFrame,
    columns: Iterable[str] = DEFAULT_EXPORT_COLUMNS,
) -> bytes:
    """Return a compact, Excel-friendly CSV containing only approved columns."""
    approved_columns = [column for column in columns if column in frame.columns]
    export_frame = frame.loc[:, approved_columns].copy()
    text_columns = export_frame.select_dtypes(include=["object", "string"]).columns
    for column in text_columns:
        export_frame[column] = export_frame[column].map(neutralize_spreadsheet_formula)
    return export_frame.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
