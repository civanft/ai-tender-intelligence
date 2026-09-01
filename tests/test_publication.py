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
from tender_intelligence.publication import export_publication, restore_publication

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
