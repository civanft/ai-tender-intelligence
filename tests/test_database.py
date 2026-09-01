from tender_intelligence.database import (
    connect_database,
    initialize_database,
    read_notice_records,
    sync_notices,
    upsert_notices,
)


def sample_record(
    score: float = 75.0,
    *,
    notice_id: str = "123456-2026",
    fetched_at: str = "2026-09-01T00:00:00+00:00",
):
    return {
        "notice_id": notice_id,
        "publication_date": "2026-09-01",
        "title": "Data platform",
        "buyer_name": "Example buyer",
        "buyer_country": "BEL",
        "sector": "IT services",
        "cpv_codes": ["72322000"],
        "place_codes": ["BEL"],
        "estimated_value": 100_000,
        "currency": "EUR",
        "deadline_date": "2026-10-01",
        "notice_type": "cn-standard",
        "procedure_type": "open",
        "ted_url": f"https://ted.europa.eu/en/notice/-/detail/{notice_id}",
        "description": "Data management services",
        "primary_theme": "Data engineering & platforms",
        "matched_keywords": {},
        "matched_cpv": {"Data engineering & platforms": [{"code": "72322000"}]},
        "classification_score": 3.5,
        "is_relevant": True,
        "opportunity_score": score,
        "score_explanation": {"total": score, "components": {}},
        "raw_notice": {"publication-number": "123456-2026"},
        "fetched_at": fetched_at,
    }


def test_upsert_updates_existing_notice(tmp_path):
    connection = connect_database(tmp_path / "test.db")
    initialize_database(connection)

    assert upsert_notices(connection, [sample_record(75)]) == 1
    assert upsert_notices(connection, [sample_record(82)]) == 1

    row = connection.execute(
        "SELECT COUNT(*) AS count, opportunity_score FROM tender_notices"
    ).fetchone()
    connection.close()

    assert row["count"] == 1
    assert row["opportunity_score"] == 82


def test_sync_notices_tracks_new_unchanged_and_updated(tmp_path):
    connection = connect_database(tmp_path / "test.db")
    initialize_database(connection)

    first = sync_notices(connection, [sample_record(75)], close_missing=False)
    second = sync_notices(connection, [sample_record(75)], close_missing=False)
    third = sync_notices(connection, [sample_record(82)], close_missing=False)
    rows = read_notice_records(connection)
    connection.close()

    assert first == {"new": 1, "updated": 0, "unchanged": 0, "closed": 0}
    assert second == {"new": 0, "updated": 0, "unchanged": 1, "closed": 0}
    assert third == {"new": 0, "updated": 1, "unchanged": 0, "closed": 0}
    assert rows[0]["lifecycle_status"] == "updated"
    assert rows[0]["first_seen_at"] == "2026-09-01T00:00:00+00:00"
    assert rows[0]["last_seen_at"] == "2026-09-01T00:00:00+00:00"


def test_complete_active_sync_closes_notice_that_disappears(tmp_path):
    connection = connect_database(tmp_path / "test.db")
    initialize_database(connection)
    sync_notices(
        connection,
        [sample_record(), sample_record(notice_id="999999-2026")],
        close_missing=False,
    )

    stats = sync_notices(
        connection,
        [sample_record(fetched_at="2026-09-02T00:00:00+00:00")],
        close_missing=True,
        countries=["BEL"],
        observed_at="2026-09-02T00:00:00+00:00",
    )
    rows = {row["notice_id"]: row for row in read_notice_records(connection)}
    connection.close()

    assert stats["closed"] == 1
    assert rows["123456-2026"]["lifecycle_status"] == "unchanged"
    assert rows["999999-2026"]["lifecycle_status"] == "closed"
    assert rows["999999-2026"]["closed_at"] == "2026-09-02T00:00:00+00:00"


def test_sql_values_cannot_escape_parameterized_queries(tmp_path):
    connection = connect_database(tmp_path / "test.db")
    initialize_database(connection)
    malicious_id = "x'); DROP TABLE tender_notices; --"

    sync_notices(
        connection,
        [sample_record(notice_id=malicious_id)],
        close_missing=False,
    )
    sync_notices(
        connection,
        [],
        close_missing=True,
        countries=["BEL') OR 1=1; --"],
        observed_at="2026-09-02T00:00:00+00:00",
    )

    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tender_notices'"
    ).fetchall()
    stored = connection.execute(
        "SELECT notice_id FROM tender_notices WHERE notice_id=?", (malicious_id,)
    ).fetchone()
    connection.close()

    assert tables
    assert stored["notice_id"] == malicious_id
