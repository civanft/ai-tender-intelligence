import json
import sqlite3

from tender_intelligence.pipeline import run_pipeline


def raw_notice(notice_id="123456-2026"):
    return {
        "publication-number": notice_id,
        "publication-date": "2026-09-01+02:00",
        "notice-title": {"eng": "Machine learning data platform"},
        "buyer-name": {"eng": ["Example buyer"]},
        "buyer-country": ["BEL"],
        "classification-cpv": ["72316000"],
        "deadline-receipt-tender-date-lot": ["2026-10-01+02:00"],
        "estimated-value-proc": "100000",
        "estimated-value-cur-proc": "EUR",
        "links": {"html": {"ENG": f"https://example.test/{notice_id}"}},
    }


class PipelineClient:
    base_url = "https://example.test/search"

    def __init__(self, notices):
        self.notices = notices

    def validate_query(self, _query, *, scope):
        del scope
        return {"timedOut": False}

    def search_all(self, _query, *, page_size, max_notices, scope):
        del page_size, max_notices, scope
        return {
            "totalNoticeCount": len(self.notices),
            "notices": self.notices,
            "fetchedPageCount": 2,
            "isComplete": True,
        }


def test_pipeline_publishes_complete_fetch_and_closes_missing_notice(tmp_path):
    db_path = tmp_path / "processed" / "tenders.db"
    raw_dir = tmp_path / "raw"
    published_dir = tmp_path / "published"

    first = run_pipeline(
        countries=["BEL"], client=PipelineClient([raw_notice()]),
        db_path=db_path, raw_dir=raw_dir, published_dir=published_dir,
    )
    second = run_pipeline(
        countries=["BEL"], client=PipelineClient([]),
        db_path=db_path, raw_dir=raw_dir, published_dir=published_dir,
    )
    payload = json.loads((published_dir / "tenders.json").read_text(encoding="utf-8"))

    assert first["fetched_page_count"] == 2
    assert first["lifecycle"] == {"new": 1, "updated": 0, "unchanged": 0, "closed": 0}
    assert second["lifecycle"]["closed"] == 1
    assert payload["notices"][0]["lifecycle_status"] == "closed"
    assert (published_dir / "tenders.parquet").exists()

    with sqlite3.connect(db_path) as connection:
        audit = connection.execute(
            "SELECT fetched_page_count, is_complete, new_count, updated_count, "
            "closed_count, publication_json_path, publication_parquet_path "
            "FROM fetch_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
    assert audit[:5] == (2, 1, 0, 0, 1)
    assert audit[5] == str(published_dir / "tenders.json")
    assert audit[6] == str(published_dir / "tenders.parquet")
