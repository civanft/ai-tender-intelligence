from tender_intelligence.data_source import load_dashboard_data
from tender_intelligence.database import connect_database, initialize_database, sync_notices
from tender_intelligence.publication import export_publication

from test_database import sample_record


def test_dashboard_prefers_local_sqlite(tmp_path):
    database_path = tmp_path / "tenders.db"
    connection = connect_database(database_path)
    initialize_database(connection)
    sync_notices(connection, [sample_record(82)], close_missing=False)
    connection.close()

    frame, source = load_dashboard_data(
        database_path=database_path,
        parquet_path=tmp_path / "missing.parquet",
        json_path=tmp_path / "missing.json",
    )

    assert source == "Local SQLite"
    assert frame.loc[0, "opportunity_score"] == 82


def test_dashboard_falls_back_from_parquet_to_json(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    paths = export_publication(
        source,
        tmp_path / "published",
        metadata={"generated_at": "2026-09-01T00:00:00+00:00"},
    )
    source.close()

    parquet_frame, parquet_source = load_dashboard_data(
        database_path=tmp_path / "missing.db",
        parquet_path=paths["parquet"],
        json_path=paths["json"],
    )
    paths["parquet"].unlink()
    json_frame, json_source = load_dashboard_data(
        database_path=tmp_path / "missing.db",
        parquet_path=paths["parquet"],
        json_path=paths["json"],
    )

    assert parquet_source == "Published Parquet"
    assert json_source == "Published JSON"
    assert parquet_frame.loc[0, "lifecycle_status"] == "new"
    assert json_frame.loc[0, "matched_keywords_json"] == "{}"


def test_dashboard_skips_an_empty_sqlite_shell_when_publication_exists(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    paths = export_publication(source, tmp_path / "published", metadata={})
    source.close()

    empty_database = tmp_path / "empty.db"
    empty = connect_database(empty_database)
    initialize_database(empty)
    empty.close()

    frame, source_label = load_dashboard_data(
        database_path=empty_database,
        parquet_path=paths["parquet"],
        json_path=paths["json"],
    )

    assert source_label == "Published Parquet"
    assert frame["notice_id"].tolist() == ["123456-2026"]
