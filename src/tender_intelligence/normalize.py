from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit


LANGUAGE_PREFERENCE = ("eng", "en", "ita", "nld", "fra", "fin")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
NOTICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
TRUSTED_TED_HOSTS = frozenset({"ted.europa.eu"})
MAX_TITLE_CHARS = 500
MAX_BUYER_CHARS = 500
MAX_DESCRIPTION_CHARS = 20_000
MAX_LIST_ITEMS = 100


def clean_public_text(value: Any, *, max_chars: int) -> str:
    """Normalize display text and remove invisible/control characters."""
    normalized = unicodedata.normalize("NFC", str(value))
    cleaned = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"}
        or unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )
    return cleaned.strip()[:max_chars]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def unique_strings(
    value: Any, *, max_items: int = MAX_LIST_ITEMS, max_chars: int = 128
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in as_list(value):
        text = clean_public_text(item, max_chars=max_chars)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
            if len(result) >= max_items:
                break
    return result


def multilingual_text(value: Any, *, max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """Pick a deterministic display string from a TED multilingual value."""
    if value is None:
        return ""
    if isinstance(value, str):
        return clean_public_text(value, max_chars=max_chars)
    if isinstance(value, list):
        pieces = []
        for item in value[:MAX_LIST_ITEMS]:
            text = clean_public_text(item, max_chars=max_chars)
            if text:
                pieces.append(text)
        joined = " ".join(pieces)
        return clean_public_text(joined, max_chars=max_chars)
    if not isinstance(value, dict):
        return clean_public_text(value, max_chars=max_chars)

    normalized_keys = {str(key).lower(): key for key in value}
    ordered_keys = [
        normalized_keys[language]
        for language in LANGUAGE_PREFERENCE
        if language in normalized_keys
    ]
    ordered_keys.extend(key for key in sorted(value) if key not in ordered_keys)
    for key in ordered_keys:
        text = multilingual_text(value[key], max_chars=max_chars)
        if text:
            return text
    return ""


def all_multilingual_text(
    value: Any, *, max_chars: int = MAX_DESCRIPTION_CHARS
) -> str:
    """Join all language values for rule matching while removing duplicates."""
    if not isinstance(value, dict):
        return multilingual_text(value, max_chars=max_chars)
    pieces: list[str] = []
    seen: set[str] = set()
    for key in sorted(value):
        text = multilingual_text(value[key], max_chars=max_chars)
        if text and text not in seen:
            seen.add(text)
            pieces.append(text)
    return clean_public_text(" ".join(pieces), max_chars=max_chars)


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
        parsed = float(item.replace(" ", ""))
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    except ValueError:
        return None


def _fallback_ted_url(notice_id: str) -> str:
    safe_notice_id = quote(notice_id, safe="-._")
    return f"https://ted.europa.eu/en/notice/-/detail/{safe_notice_id}"


def is_valid_notice_id(value: Any) -> bool:
    return isinstance(value, str) and NOTICE_ID_PATTERN.fullmatch(value) is not None


def trusted_ted_url(candidate: Any, notice_id: str) -> str:
    """Return only canonical HTTPS TED links, otherwise a safe TED fallback."""
    fallback = _fallback_ted_url(notice_id)
    if not isinstance(candidate, str):
        return fallback
    cleaned = clean_public_text(candidate, max_chars=2_048)
    try:
        parsed = urlsplit(cleaned)
        port = parsed.port
    except ValueError:
        return fallback
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() not in TRUSTED_TED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        return fallback
    netloc = "ted.europa.eu" if port is None else "ted.europa.eu:443"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


def _ted_url(links: Any, notice_id: str) -> str:
    if isinstance(links, dict):
        html = links.get("html", {})
        if isinstance(html, dict):
            for language in ("ENG", "ITA", "NLD", "FRA", "FIN"):
                if html.get(language):
                    return trusted_ted_url(str(html[language]), notice_id)
            if html:
                return trusted_ted_url(str(next(iter(html.values()))), notice_id)
    return _fallback_ted_url(notice_id)


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
    if not is_valid_notice_id(notice_id):
        raise ValueError("TED notice has an invalid publication-number.")

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
        "title": multilingual_text(
            notice.get("notice-title"), max_chars=MAX_TITLE_CHARS
        ) or "Untitled TED notice",
        "buyer_name": multilingual_text(
            notice.get("buyer-name"), max_chars=MAX_BUYER_CHARS
        ) or None,
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
        "description": clean_public_text(
            description, max_chars=MAX_DESCRIPTION_CHARS
        ) or None,
        "raw_notice": notice,
        "fetched_at": fetched_at,
    }
