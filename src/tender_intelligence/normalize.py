from __future__ import annotations

import json
import re
from typing import Any


LANGUAGE_PREFERENCE = ("eng", "en", "ita", "nld", "fra", "fin")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def unique_strings(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in as_list(value):
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def multilingual_text(value: Any) -> str:
    """Pick a deterministic display string from a TED multilingual value."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    if not isinstance(value, dict):
        return str(value).strip()

    normalized_keys = {str(key).lower(): key for key in value}
    ordered_keys = [
        normalized_keys[language]
        for language in LANGUAGE_PREFERENCE
        if language in normalized_keys
    ]
    ordered_keys.extend(key for key in sorted(value) if key not in ordered_keys)
    for key in ordered_keys:
        text = multilingual_text(value[key])
        if text:
            return text
    return ""


def all_multilingual_text(value: Any) -> str:
    """Join all language values for rule matching while removing duplicates."""
    if not isinstance(value, dict):
        return multilingual_text(value)
    pieces: list[str] = []
    seen: set[str] = set()
    for key in sorted(value):
        text = multilingual_text(value[key])
        if text and text not in seen:
            seen.add(text)
            pieces.append(text)
    return " ".join(pieces)


def iso_date(value: Any) -> str | None:
    dates: list[str] = []
    for item in as_list(value):
        match = DATE_PATTERN.match(str(item).strip())
        if match:
            dates.append(match.group(0))
    return min(dates) if dates else None


def first_string(value: Any) -> str | None:
    values = unique_strings(value)
    return values[0] if values else None


def to_float(value: Any) -> float | None:
    item = first_string(value)
    if item is None:
        return None
    try:
        return float(item.replace(" ", ""))
    except ValueError:
        return None


def _ted_url(links: Any, notice_id: str) -> str:
    if isinstance(links, dict):
        html = links.get("html", {})
        if isinstance(html, dict):
            for language in ("ENG", "ITA", "NLD", "FRA", "FIN"):
                if html.get(language):
                    return str(html[language])
            if html:
                return str(next(iter(html.values())))
    return f"https://ted.europa.eu/en/notice/-/detail/{notice_id}"


def _sector(cpv_codes: list[str]) -> str:
    mappings = (
        ("48", "Software packages and information systems"),
        ("72", "IT services"),
        ("30", "Computing equipment and supplies"),
        ("73", "Research and development"),
    )
    for prefix, label in mappings:
        if any(code.startswith(prefix) for code in cpv_codes):
            return label
    return "Other"


def normalize_notice(notice: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    notice_id = str(notice.get("publication-number", "")).strip()
    if not notice_id:
        raise ValueError("TED notice is missing publication-number.")

    cpv_codes = unique_strings(notice.get("classification-cpv"))
    if not cpv_codes:
        cpv_codes = unique_strings(notice.get("main-classification-proc"))

    description_parts = [
        all_multilingual_text(notice.get("description-proc")),
        all_multilingual_text(notice.get("description-lot")),
    ]
    description = " ".join(part for part in description_parts if part)

    return {
        "notice_id": notice_id,
        "publication_date": iso_date(notice.get("publication-date")),
        "title": multilingual_text(notice.get("notice-title")) or "Untitled TED notice",
        "buyer_name": multilingual_text(notice.get("buyer-name")) or None,
        "buyer_country": first_string(notice.get("buyer-country")),
        "sector": _sector(cpv_codes),
        "cpv_codes": cpv_codes,
        "place_codes": unique_strings(notice.get("place-of-performance")),
        "estimated_value": to_float(notice.get("estimated-value-proc")),
        "currency": first_string(notice.get("estimated-value-cur-proc")),
        "deadline_date": iso_date(notice.get("deadline-receipt-tender-date-lot")),
        "notice_type": first_string(notice.get("notice-type")),
        "procedure_type": first_string(notice.get("procedure-type")),
        "ted_url": _ted_url(notice.get("links"), notice_id),
        "description": description or None,
        "raw_notice": notice,
        "fetched_at": fetched_at,
    }
