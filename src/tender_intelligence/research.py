"""Evidence-based research tools. No network calls or user-data persistence."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import html
import json
import math
import unicodedata
from typing import Any

import pandas as pd

from .normalize import is_valid_notice_id, trusted_ted_url

STAGES = ("Watching", "Researching", "Ready for review", "Archived")
CHECKS = {
    "scope": "Scope and deliverables checked",
    "eligibility": "Eligibility and exclusions checked",
    "documents": "Official procurement documents reviewed",
    "resources": "Capacity and partners assessed",
    "deadline": "Submission deadline verified at the source",
}
MAX_WORKSPACE_BYTES = 500_000
MAX_SAVED = 100
DEFAULT_WEIGHTS = {"market": 20, "theme": 30, "evidence": 20, "runway": 20, "budget": 10}


def text(value: Any, limit: int = 6000) -> str:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ""
    return "".join(c for c in str(value)[:limit] if unicodedata.category(c) not in {"Cc", "Cf", "Cs"} or c in "\n\t")


def json_field(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def deadline_days(value: Any, today: date) -> int | None:
    try:
        return (date.fromisoformat(text(value)) - today).days
    except ValueError:
        return None


def deadline_label(record: dict | pd.Series, today: date) -> str:
    if record.get("lifecycle_status") == "closed":
        return "Closed in the latest complete refresh"
    days = deadline_days(record.get("deadline_date"), today)
    if days is None:
        return "Deadline not disclosed"
    if days < 0:
        return f"Deadline passed {abs(days)} days ago"
    return "Due today" if days == 0 else f"{days} days remaining"


def research_checks(record: dict | pd.Series, today: date) -> list[dict[str, str]]:
    days = deadline_days(record.get("deadline_date"), today)
    warnings = []
    if record.get("lifecycle_status") == "closed":
        warnings.append({"label": "Availability", "detail": "Absent from the latest complete ACTIVE refresh. Verify the official notice."})
    if days is None:
        warnings.append({"label": "Deadline", "detail": "No usable submission date. Check the official documents before planning."})
    elif days < 0:
        warnings.append({"label": "Deadline", "detail": f"Normalized deadline passed {abs(days)} days ago. Do not treat this as an open bid."})
    elif days <= 7:
        warnings.append({"label": "Preparation time", "detail": f"Only {days} days remain; verify the exact time and time zone at TED."})
    amount = record.get("estimated_value")
    if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount <= 0 or not text(record.get("currency")):
        warnings.append({"label": "Value", "detail": "Budget or currency is missing. No budget suitability conclusion is possible."})
    if not text(record.get("description")):
        warnings.append({"label": "Scope", "detail": "The normalized description is empty; consult the source documents."})
    warnings.append({"label": "Eligibility", "detail": "Certifications, exclusions, language and legal eligibility have not been assessed by this tool."})
    return warnings


def actionable(frame: pd.DataFrame, today: date) -> pd.DataFrame:
    days = frame["deadline_date"].map(lambda v: deadline_days(v, today))
    return frame.loc[frame["lifecycle_status"].ne("closed") & (days.isna() | days.ge(0))].copy()


def related_notices(frame: pd.DataFrame, record: dict | pd.Series, today: date, limit: int = 5) -> pd.DataFrame:
    candidates = actionable(frame, today)
    source_codes = {str(v)[:5] for v in json_field(record.get("cpv_codes_json"), []) if isinstance(v, str)}
    rows = []
    for _, candidate in candidates.iterrows():
        if candidate["notice_id"] == record["notice_id"]:
            continue
        reasons, points = [], 0
        for field, weight, label in (("primary_theme", 45, "Same technology theme"), ("buyer_country", 15, "Same buyer market"), ("buyer_name", 15, "Same disclosed buyer name")):
            if text(record.get(field)) and candidate.get(field) == record.get(field):
                points += weight
                reasons.append(label)
        codes = {str(v)[:5] for v in json_field(candidate.get("cpv_codes_json"), []) if isinstance(v, str)}
        common = sorted(source_codes & codes)
        if common:
            points += 25
            reasons.append("Shared CPV family: " + ", ".join(common))
        # A country match alone is not meaningful enough to recommend a notice.
        if points >= 25:
            rows.append({"notice_id": candidate["notice_id"], "similarity": points, "reason": "; ".join(reasons)})
    if not rows:
        return pd.DataFrame(columns=["notice_id", "similarity", "reason"])
    return pd.DataFrame(rows).sort_values(["similarity", "notice_id"], ascending=[False, True]).head(limit)


def scenario_scores(frame: pd.DataFrame, markets: list[str], themes: list[str], weights: dict[str, int], today: date) -> pd.DataFrame:
    if set(weights) != set(DEFAULT_WEIGHTS) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 100 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Choose non-negative weights with a total greater than zero.")
    result = frame.copy()
    normalized = {key: 100 * value / sum(weights.values()) for key, value in weights.items()}
    result["fit_market"] = result["buyer_country"].isin(markets).astype(float) * normalized["market"]
    result["fit_theme"] = result["primary_theme"].isin(themes).astype(float) * normalized["theme"]
    result["fit_evidence"] = pd.to_numeric(result["classification_score"], errors="coerce").fillna(0).clip(0, 10) / 10 * normalized["evidence"]
    def runway(value: Any) -> float:
        days = deadline_days(value, today)
        if days is None:
            return 0
        return min(1, max(0, days / 45))
    result["fit_runway"] = pd.to_numeric(result["deadline_date"].map(runway), errors="coerce").astype(float) * normalized["runway"]
    amount = pd.to_numeric(result["estimated_value"], errors="coerce")
    currency = result["currency"].map(text).ne("")
    result["fit_budget"] = (amount.gt(0) & currency).astype(float) * normalized["budget"]
    result["scenario_fit"] = result[[f"fit_{k}" for k in DEFAULT_WEIGHTS]].sum(axis=1).round(1)
    return result.sort_values(["scenario_fit", "notice_id"], ascending=[False, True])


def buyer_summary(frame: pd.DataFrame, today: date) -> pd.DataFrame:
    rows = []
    for (country, buyer), group in frame.groupby(["buyer_country", "buyer_name"], dropna=False):
        if not text(buyer):
            continue
        eur = group.loc[group["currency"].eq("EUR"), "estimated_value"]
        rows.append({"buyer_country": country, "buyer_name": buyer, "notices": len(group), "screened": int(group["is_relevant"].sum()), "themes": group["primary_theme"].nunique(), "upcoming": int(group["deadline_date"].map(lambda v: (d := deadline_days(v, today)) is not None and d >= 0).sum()), "disclosed_eur": eur.sum(min_count=1)})
    return pd.DataFrame(rows).sort_values(["screened", "notices", "buyer_name"], ascending=[False, False, True]) if rows else pd.DataFrame()


def fresh_workspace() -> dict:
    return {"schema_version": 1, "saved": {}, "views": {}}


def _reject_constant(value: str) -> None:
    raise ValueError("Workspace contains an invalid number.")


def validate_workspace(payload: Any) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "saved", "views"} or type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("This is not a supported Tender Meridian workspace.")
    saved, views = payload["saved"], payload["views"]
    if not isinstance(saved, dict) or len(saved) > MAX_SAVED or not isinstance(views, dict) or len(views) > 20:
        raise ValueError("Workspace exceeds the saved-record or view limit.")
    clean = fresh_workspace()
    for notice_id, entry in saved.items():
        if not is_valid_notice_id(notice_id) or not isinstance(entry, dict) or set(entry) != {"stage", "note", "checks"}:
            raise ValueError("A saved notice has an invalid format.")
        if entry["stage"] not in STAGES or not isinstance(entry["note"], str) or len(entry["note"]) > 4000 or not isinstance(entry["checks"], dict) or set(entry["checks"]) - set(CHECKS) or any(type(v) is not bool for v in entry["checks"].values()):
            raise ValueError("A saved notice contains invalid research notes or checks.")
        clean["saved"][notice_id] = {"stage": entry["stage"], "note": text(entry["note"], 4000), "checks": entry["checks"].copy()}
    for name, view in views.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 60 or not isinstance(view, dict) or set(view) != {"query", "countries", "themes", "lifecycles", "relevant", "score", "sort"}:
            raise ValueError("A saved search has an invalid format.")
        if not isinstance(view["query"], str) or len(view["query"]) > 200 or type(view["relevant"]) is not bool or type(view["score"]) is not int or not 0 <= view["score"] <= 100 or view["sort"] not in ("Highest profile fit", "Newest publication", "Nearest deadline", "Largest disclosed value"):
            raise ValueError("A saved search has invalid filters.")
        for field in ("countries", "themes", "lifecycles"):
            if not isinstance(view[field], list) or len(view[field]) > 30 or any(not isinstance(v, str) or len(v) > 120 for v in view[field]):
                raise ValueError("A saved search has invalid selections.")
        clean["views"][text(name, 60)] = {**view, "query": text(view["query"], 200)}
    return clean


def import_workspace(raw: bytes) -> dict:
    if len(raw) > MAX_WORKSPACE_BYTES:
        raise ValueError("Workspace file must be smaller than 500 KB.")
    try:
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        return validate_workspace(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Upload a valid UTF-8 workspace JSON file.") from exc


def export_workspace(workspace: dict) -> bytes:
    raw = json.dumps(validate_workspace(workspace), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_WORKSPACE_BYTES:
        raise ValueError("Workspace exceeds 500 KB. Shorten notes before saving more research.")
    return raw


def _ics_escape(value: Any) -> str:
    return text(value, 400).replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold_ics(line: str) -> str:
    # RFC 5545 counts octets, not Unicode characters, including the leading space.
    parts, part = [], ""
    for char in line:
        if len((part + char).encode("utf-8")) > 75:
            parts.append(part)
            part = " "
        part += char
    return "\r\n".join(parts + [part])


def deadline_calendar(frame: pd.DataFrame, today: date) -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tender Meridian//Deadline desk//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    eligible = actionable(frame, today)
    eligible = eligible.loc[eligible["deadline_date"].map(lambda v: deadline_days(v, today)).notna()]
    eligible = eligible.sort_values("deadline_date").head(MAX_SAVED)
    for _, record in eligible.iterrows():
        days = deadline_days(record.get("deadline_date"), today)
        if days is None or not is_valid_notice_id(record["notice_id"]):
            continue
        day = today + timedelta(days=days)
        url = trusted_ted_url(record.get("ted_url"), record["notice_id"])
        lines += ["BEGIN:VEVENT", f"UID:{record['notice_id']}@tender-intelligence", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}", "SUMMARY:" + _ics_escape("TED deadline · " + text(record["title"])), "DESCRIPTION:" + _ics_escape("Date-only planning reminder. Verify exact deadline and time zone in the official notice. " + url), "URL:" + url, "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold_ics(line) for line in lines) + "\r\n").encode("utf-8")


def research_brief(frame: pd.DataFrame, today: date, title: str = "Research brief") -> bytes:
    """Standalone, escaped HTML; private notes deliberately excluded."""
    esc = lambda v: html.escape(text(v))
    articles = []
    for _, row in frame.head(MAX_SAVED).iterrows():
        url = html.escape(trusted_ted_url(row.get("ted_url"), row["notice_id"]), quote=True)
        issues = "".join(f"<li><strong>{esc(w['label'])}:</strong> {esc(w['detail'])}</li>" for w in research_checks(row, today))
        value = text(row.get("estimated_value")) or "Not disclosed"
        articles.append(f"<article><small>{esc(row['notice_id'])} · {esc(row['buyer_country'])}</small><h2>{esc(row['title'])}</h2><p>{esc(row['buyer_name'])}</p><p>{esc(row['primary_theme'])} · {esc(deadline_label(row, today))}</p><p>Procedure estimate: {esc(value)} {esc(row.get('currency'))}</p><h3>Questions to verify</h3><ul>{issues}</ul><a href='{url}' rel='noopener noreferrer'>Official TED record</a></article>")
    page = f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)} · Tender Meridian</title><style>body{{font:16px/1.7 system-ui,sans-serif;color:#1b304c;max-width:900px;margin:40px auto;padding:20px}}h1,h2{{font-family:Georgia,serif}}article{{border-top:1px solid #ccd7e6;padding:24px 0}}small{{color:#52667b}}a{{color:#315eaa}}p,li{{overflow-wrap:anywhere}}</style><header><small>TENDER MERIDIAN · EU TED</small><h1>{esc(title)}</h1><p>Prepared {today.isoformat()} · {len(frame.head(MAX_SAVED))} notices</p><p>This is a snapshot research aid. Estimates are not spend or won contracts. Verify requirements, eligibility and exact deadlines in official documents. Personal notes are excluded.</p></header>{''.join(articles)}</html>"
    return page.encode("utf-8")
