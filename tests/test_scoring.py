from datetime import date

from tender_intelligence.config import load_profile
from tender_intelligence.scoring import score_opportunity


def test_score_is_sum_of_named_profile_components():
    record = {
        "buyer_country": "BEL",
        "deadline_date": "2026-11-01",
        "estimated_value": 500_000,
        "currency": "EUR",
    }
    classification = {
        "primary_theme": "AI & machine learning",
        "classification_score": 5.0,
    }

    result = score_opportunity(
        record,
        classification,
        load_profile(),
        assessed_on=date(2026, 9, 1),
    )

    assert result["total"] == 90
    assert result["components"]["country_fit"]["points"] == 20
    assert result["components"]["theme_fit"]["points"] == 30
    assert result["components"]["classification_evidence"]["points"] == 10
    assert result["components"]["deadline_runway"]["points"] == 20
    assert result["components"]["budget_clarity"]["points"] == 10
    assert "not a probability" in result["disclaimer"]


def test_expired_deadline_receives_no_runway_points():
    result = score_opportunity(
        {
            "buyer_country": "FIN",
            "deadline_date": "2026-08-01",
            "estimated_value": None,
            "currency": None,
        },
        {"primary_theme": "Other digital", "classification_score": 0},
        load_profile(),
        assessed_on=date(2026, 9, 1),
    )

    assert result["components"]["deadline_runway"]["points"] == 0
    assert result["components"]["budget_clarity"]["points"] == 0
