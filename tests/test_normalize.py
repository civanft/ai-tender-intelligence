import pytest

from tender_intelligence.normalize import normalize_notice, trusted_ted_url


def test_normalize_prefers_english_and_earliest_deadline():
    raw = {
        "publication-number": "123456-2026",
        "publication-date": "2026-08-30+02:00",
        "notice-title": {"ita": "Titolo", "eng": "English title"},
        "buyer-name": {"ita": ["Comune Demo"], "eng": ["Demo Municipality"]},
        "buyer-country": ["ITA"],
        "classification-cpv": ["72316000", "72316000"],
        "deadline-receipt-tender-date-lot": [
            "2026-10-15+02:00",
            "2026-10-01+02:00",
        ],
        "estimated-value-proc": "1200000",
        "estimated-value-cur-proc": "EUR",
        "place-of-performance": ["ITI43", "ITA", "ITA"],
        "links": {"html": {"ENG": "https://ted.europa.eu/en/notice/-/detail/123456-2026"}},
    }

    normalized = normalize_notice(raw, "2026-09-01T00:00:00+00:00")

    assert normalized["title"] == "English title"
    assert normalized["buyer_name"] == "Demo Municipality"
    assert normalized["deadline_date"] == "2026-10-01"
    assert normalized["publication_date"] == "2026-08-30"
    assert normalized["cpv_codes"] == ["72316000"]
    assert normalized["place_codes"] == ["ITI43", "ITA"]
    assert normalized["estimated_value"] == 1_200_000.0
    assert normalized["ted_url"] == "https://ted.europa.eu/en/notice/-/detail/123456-2026"


@pytest.mark.parametrize(
    "candidate",
    [
        "javascript:alert(1)",
        "https://evil.example/steal",
        "https://ted.europa.eu@evil.example/steal",
        "https://ted.europa.eu\\@evil.example/steal",
    ],
)
def test_untrusted_ted_links_fall_back_to_official_record(candidate):
    assert trusted_ted_url(candidate, "123456-2026") == (
        "https://ted.europa.eu/en/notice/-/detail/123456-2026"
    )


def test_normalize_rejects_malformed_id_and_removes_control_characters():
    with pytest.raises(ValueError, match="invalid publication-number"):
        normalize_notice(
            {"publication-number": "123456-2026\nInjected"},
            "2026-09-01T00:00:00+00:00",
        )

    normalized = normalize_notice(
        {
            "publication-number": "123456-2026",
            "notice-title": {"eng": "Safe\u202eexe.html\x00 title"},
        },
        "2026-09-01T00:00:00+00:00",
    )

    assert normalized["title"] == "Safeexe.html title"
