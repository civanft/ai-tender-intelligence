import json
from copy import deepcopy

import pandas as pd
import pytest

from tender_intelligence.database import (
    connect_database,
    initialize_database,
    read_notice_records,
    sync_notices,
)
from tender_intelligence.publication import (
    export_publication,
    restore_publication,
    validate_publication_frame,
    load_validated_publication,
)


def test_large_publication_uses_gzip_and_restores_without_stale_json(tmp_path, monkeypatch):
    from tender_intelligence import publication
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    first = export_publication(source, tmp_path / "published", metadata={})
    assert first["json"].suffix == ".json"
    monkeypatch.setattr(publication, "MAX_PLAIN_JSON_BYTES", 100)
    large = export_publication(source, tmp_path / "published", metadata={})
    source.close()
    assert large["json"].name == "tenders.json.gz"
    assert not first["json"].exists()
    assert load_validated_publication(first["json"])["metadata"]["notice_count"] == 1
    restored = connect_database(tmp_path / "restored.db")
    initialize_database(restored)
    assert restore_publication(restored, first["json"]) == 1
    restored.close()


def test_gzip_publication_decompression_is_bounded(tmp_path, monkeypatch):
    import gzip
    from tender_intelligence import publication
    path = tmp_path / "tenders.json.gz"
    path.write_bytes(gzip.compress(b" " * 1000))
    monkeypatch.setattr(publication, "MAX_DECOMPRESSED_PUBLICATION_BYTES", 100)
    with pytest.raises(ValueError, match="Decompressed"):
        load_validated_publication(path)

from test_database import sample_record


def test_publication_exports_json_and_parquet_and_restores_state(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)

    result = export_publication(
        source,
        tmp_path / "published",
        metadata={"generated_at": "2026-09-01T00:00:00+00:00", "scope": "ACTIVE"},
    )
    payload = json.loads(result["json"].read_text(encoding="utf-8"))
    parquet = pd.read_parquet(result["parquet"])
    source.close()

    assert payload["schema_version"] == "1.0"
    assert payload["notices"][0]["notice_id"] == "123456-2026"
    assert payload["notices"][0]["score_explanation"]["total"] == 75
    assert parquet.loc[0, "lifecycle_status"] == "new"

    restored = connect_database(tmp_path / "restored.db")
    initialize_database(restored)
    assert restore_publication(restored, result["json"]) == 1
    restored_rows = read_notice_records(restored)
    restored.close()

    assert restored_rows[0]["notice_id"] == "123456-2026"
    assert restored_rows[0]["lifecycle_status"] == "new"
    assert restored_rows[0]["content_hash"] == payload["notices"][0]["content_hash"]


@pytest.mark.parametrize("mutation", ["schema", "count", "hash", "url", "id"])
def test_restore_rejects_tampered_or_untrusted_publications(tmp_path, mutation):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    result = export_publication(source, tmp_path / "published", metadata={})
    source.close()

    payload = json.loads(result["json"].read_text(encoding="utf-8"))
    tampered = deepcopy(payload)
    if mutation == "schema":
        tampered["schema_version"] = "999"
    elif mutation == "count":
        tampered["metadata"]["notice_count"] = 99
    elif mutation == "hash":
        tampered["notices"][0]["title"] = "Tampered title"
    elif mutation == "url":
        tampered["notices"][0]["ted_url"] = "javascript:alert(1)"
    else:
        tampered["notices"][0]["notice_id"] = "123456-2026\nInjected"
    result["json"].write_text(json.dumps(tampered), encoding="utf-8")

    restored = connect_database(tmp_path / "restored.db")
    initialize_database(restored)
    with pytest.raises(ValueError):
        restore_publication(restored, result["json"])
    restored.close()


def test_publication_never_exports_extra_database_columns(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    source.execute("ALTER TABLE tender_notices ADD COLUMN private_note TEXT")
    source.execute("UPDATE tender_notices SET private_note = ?", ("private-sentinel",))
    source.commit()
    result = export_publication(source, tmp_path / "published", metadata={})
    source.close()
    text = result["json"].read_text(encoding="utf-8")
    assert "private_note" not in text
    assert "private-sentinel" not in text
    assert "private_note" not in pd.read_parquet(result["parquet"]).columns


def test_private_metadata_is_rejected_before_writing(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    with pytest.raises(ValueError, match="non-public"):
        export_publication(
            source,
            tmp_path / "published",
            metadata={"api_key": "private-sentinel"},
        )
    assert not (tmp_path / "published").exists()
    source.close()


def test_publication_loaders_reject_extra_private_fields(tmp_path):
    source = connect_database(tmp_path / "source.db")
    initialize_database(source)
    sync_notices(source, [sample_record()], close_missing=False)
    result = export_publication(source, tmp_path / "published", metadata={})
    source.close()
    frame = pd.read_parquet(result["parquet"])
    frame["private_note"] = "private-sentinel"
    with pytest.raises(ValueError):
        validate_publication_frame(frame)
    payload = json.loads(result["json"].read_text(encoding="utf-8"))
    payload["notices"][0]["private_note"] = "private-sentinel"
    result["json"].write_text(json.dumps(payload), encoding="utf-8")
    restored = connect_database(tmp_path / "restored.db")
    initialize_database(restored)
    with pytest.raises(ValueError):
        restore_publication(restored, result["json"])
    restored.close()
