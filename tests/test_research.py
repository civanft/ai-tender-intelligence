from datetime import date
import json

import pandas as pd
import pytest

from tender_intelligence.research import (
    DEFAULT_WEIGHTS, actionable, buyer_summary, deadline_calendar,
    export_workspace, fresh_workspace, import_workspace, related_notices,
    research_brief, research_checks, scenario_scores,
)

TODAY = date(2026, 10, 14)


def records():
    base = {"buyer_country": "BEL", "buyer_name": "Public buyer", "primary_theme": "Data", "deadline_date": "2026-11-01", "lifecycle_status": "new", "title": "Data services", "description": "Scope", "estimated_value": 1000., "currency": "EUR", "opportunity_score": 85., "classification_score": 5., "is_relevant": 1, "cpv_codes_json": '["72322000"]', "ted_url": "javascript:alert(1)"}
    return pd.DataFrame([{**base, "notice_id": "123456-2026"}, {**base, "notice_id": "123457-2026", "title": "Related services"}, {**base, "notice_id": "123458-2026", "deadline_date": "2026-10-01"}, {**base, "notice_id": "123459-2026", "lifecycle_status": "closed"}, {**base, "notice_id": "123460-2026", "deadline_date": None, "estimated_value": None}])


def test_time_checks_and_recommendations_exclude_expired_and_closed():
    frame = records()
    assert set(actionable(frame, TODAY)["notice_id"]) == {"123456-2026", "123457-2026", "123460-2026"}
    related = related_notices(frame, frame.iloc[0], TODAY)
    assert set(related["notice_id"]) == {"123457-2026", "123460-2026"}
    assert related.iloc[0]["similarity"] == 100
    assert "CPV family" in related.iloc[0]["reason"]
    assert any("passed" in w["detail"] for w in research_checks(frame.iloc[2], TODAY))
    assert any(w["label"] == "Value" for w in research_checks(frame.iloc[4], TODAY))


def test_scenario_weights_are_normalized_and_all_components_visible():
    frame = records()
    result = scenario_scores(frame, ["BEL"], ["Data"], DEFAULT_WEIGHTS, TODAY)
    row = result.set_index("notice_id").loc["123456-2026"]
    assert row["scenario_fit"] == 78.0  # 20 + 30 + 10 + (18/45)*20 + 10
    assert row["fit_runway"] == 8.0
    evidence_only = scenario_scores(frame, [], [], {k: (100 if k == "evidence" else 0) for k in DEFAULT_WEIGHTS}, TODAY)
    assert evidence_only.iloc[0]["scenario_fit"] == 50
    with pytest.raises(ValueError):
        scenario_scores(frame, [], [], {k: 0 for k in DEFAULT_WEIGHTS}, TODAY)
    with pytest.raises(ValueError):
        scenario_scores(frame, [], [], {**DEFAULT_WEIGHTS, "market": float("nan")}, TODAY)


def test_workspace_roundtrip_and_strict_private_contract():
    workspace = fresh_workspace()
    workspace["saved"]["123456-2026"] = {"stage": "Researching", "note": "Private question", "checks": {"scope": True}}
    imported = import_workspace(export_workspace(workspace))
    assert imported == workspace
    imported["saved"]["123456-2026"]["checks"]["scope"] = False
    assert workspace["saved"]["123456-2026"]["checks"]["scope"] is True
    invalid = {**workspace, "token": "private"}
    with pytest.raises(ValueError):
        import_workspace(json.dumps(invalid).encode())
    workspace["saved"]["123456-2026"]["checks"]["scope"] = "false"
    with pytest.raises(ValueError):
        export_workspace(workspace)
    with pytest.raises(ValueError):
        import_workspace(b"{" * 500001)
    with pytest.raises(ValueError):
        import_workspace(b'{"schema_version":NaN,"saved":{},"views":{}}')


def test_calendar_escapes_injection_and_folds_unicode_in_octets():
    frame = records()
    frame.loc[0, "title"] = "Ö" * 120 + "\r\nBEGIN:VEVENT\nURL:https://evil.example"
    cal = deadline_calendar(frame, TODAY).decode()
    assert cal.count("BEGIN:VEVENT\r\n") == 2
    assert "DTSTART;VALUE=DATE:20261101" in cal
    assert "123458-2026@" not in cal and "123459-2026@" not in cal and "123460-2026@" not in cal
    assert "javascript:" not in cal
    assert all(len(line.encode()) <= 75 for line in cal.split("\r\n"))
    assert "DTEND;VALUE=DATE:20261102" in cal


def test_research_brief_escapes_source_and_excludes_notes_and_raw_data():
    frame = records()
    frame.loc[0, "title"] = '<script>alert("x")</script>'
    frame["private_note"] = "SECRET_PRIVATE_NOTE"
    frame["raw_notice_json"] = "SECRET_RAW_CONTENT"
    brief = research_brief(frame, TODAY).decode()
    assert "<script>" not in brief
    assert "&lt;script&gt;" in brief
    assert "SECRET_PRIVATE_NOTE" not in brief and "SECRET_RAW_CONTENT" not in brief
    assert "javascript:" not in brief and "https://ted.europa.eu/" in brief


def test_buyer_profiles_separate_country_and_keep_missing_value_unknown():
    frame = records()
    frame.loc[1, "buyer_country"] = "ITA"
    frame["estimated_value"] = None
    summary = buyer_summary(frame, TODAY)
    assert len(summary) == 2
    assert summary["disclosed_eur"].isna().all()


def test_unicode_workspace_cannot_outgrow_its_import_limit():
    workspace = fresh_workspace()
    for index in range(100):
        workspace["saved"][f"{123456 + index}-2026"] = {"stage": "Watching", "note": "😀" * 4000, "checks": {}}
    with pytest.raises(ValueError, match="500 KB"):
        export_workspace(workspace)
