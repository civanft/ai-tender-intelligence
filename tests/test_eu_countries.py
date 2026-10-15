from datetime import date
import pytest

from tender_intelligence.countries import EU_COUNTRY_NAMES, EU_COUNTRY_CODES, EU_COUNTRY_COLORS
from tender_intelligence.config import load_profile, load_taxonomy
from tender_intelligence.ted_client import build_candidate_query
from tender_intelligence.scoring import score_opportunity
from tender_intelligence.normalize import normalize_notice


def test_catalogue_contains_exactly_all_eu_27_and_no_non_members():
    expected = set('AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE'.split())
    assert set(EU_COUNTRY_CODES) == expected
    assert len(EU_COUNTRY_NAMES) == len(set(EU_COUNTRY_NAMES.values())) == 27
    assert set(EU_COUNTRY_COLORS) == expected
    query = build_candidate_query(EU_COUNTRY_CODES, load_taxonomy())
    assert f"buyer-country IN ({' '.join(sorted(expected))})" in query


def test_every_eu_country_gets_equal_explicit_market_points():
    profile = load_profile()
    assert set(profile["country_points"]) == set(EU_COUNTRY_CODES)
    for code in EU_COUNTRY_CODES:
        result = score_opportunity({"buyer_country": code, "deadline_date": "2099-01-01"}, {"primary_theme": "AI & machine learning", "classification_score": 5}, profile, assessed_on=date(2026, 10, 14))
        assert result["components"]["country_fit"]["points"] == 20


def test_multibuyer_notice_uses_a_matching_eu_country_and_retains_source():
    record = normalize_notice({"publication-number": "123456-2026", "buyer-country": ["NOR", "DEU", "FRA"]}, "2026-10-14T00:00:00Z")
    assert record["buyer_country"] == "DEU"
    assert record["raw_notice"]["buyer-country"] == ["NOR", "DEU", "FRA"]


@pytest.mark.parametrize("code", ["GBR", "NOR", "CHE", "TUR"])
def test_non_eu_countries_cannot_enter_the_candidate_scope(code):
    with pytest.raises(ValueError, match="EU member-state"):
        build_candidate_query([code], load_taxonomy())
