from tender_intelligence.normalize import normalize_notice


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
        "links": {"html": {"ENG": "https://example.test/notice"}},
    }

    normalized = normalize_notice(raw, "2026-09-01T00:00:00+00:00")

    assert normalized["title"] == "English title"
    assert normalized["buyer_name"] == "Demo Municipality"
    assert normalized["deadline_date"] == "2026-10-01"
    assert normalized["publication_date"] == "2026-08-30"
    assert normalized["cpv_codes"] == ["72316000"]
    assert normalized["place_codes"] == ["ITI43", "ITA"]
    assert normalized["estimated_value"] == 1_200_000.0
    assert normalized["ted_url"] == "https://example.test/notice"
