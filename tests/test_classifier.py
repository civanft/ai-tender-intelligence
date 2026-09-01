from tender_intelligence.classifier import classify_notice
from tender_intelligence.config import load_taxonomy


def test_explicit_ai_phrase_is_relevant():
    record = {
        "title": "Machine learning platform for public transport",
        "description": "Build and monitor predictive models.",
        "cpv_codes": ["72262000"],
    }
    result = classify_notice(record, load_taxonomy())

    assert result["is_relevant"] is True
    assert result["primary_theme"] == "AI & machine learning"
    assert result["classification_score"] >= 4
    assert result["matched_keywords"]["AI & machine learning"]


def test_specific_data_cpv_is_relevant_without_keyword():
    record = {
        "title": "Framework service",
        "description": None,
        "cpv_codes": ["72316000"],
    }
    result = classify_notice(record, load_taxonomy())

    assert result["is_relevant"] is True
    assert result["primary_theme"] == "Analytics & business intelligence"


def test_broad_software_service_is_only_a_candidate():
    record = {
        "title": "Application maintenance service",
        "description": "Support and bug fixing for an existing application.",
        "cpv_codes": ["72260000"],
    }
    result = classify_notice(record, load_taxonomy())

    assert result["is_relevant"] is False
    assert result["primary_theme"] == "Other digital"
    assert result["classification_score"] == 0
