import gc
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tender_intelligence import paths
from tender_intelligence.database import connect_database, initialize_database, sync_notices
from test_database import sample_record


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Run the real UI against synthetic records, never the user's database."""
    database_path = tmp_path / "workspace.db"
    connection = connect_database(database_path)
    initialize_database(connection)
    records = []
    for index, country in enumerate(("BEL", "ITA", "FIN")):
        record = sample_record(85 - index, notice_id=f"12345{index}-2026")
        record["buyer_country"] = country
        records.append(record)
    sync_notices(connection, records, close_missing=False)
    connection.close()
    monkeypatch.setattr(paths, "DEFAULT_DB_PATH", database_path)
    monkeypatch.setattr(paths, "PUBLISHED_JSON_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(paths, "PUBLISHED_PARQUET_PATH", tmp_path / "absent.parquet")
    st.cache_data.clear()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    yield app
    st.cache_data.clear()


def test_every_workspace_destination_renders(workspace):
    for page in ("Opportunities", "Markets", "Timeline", "Dossier", "Method", "Overview"):
        workspace.radio(key="workspace_page").set_value(page).run()
        assert not workspace.exception, page
        assert workspace.radio(key="workspace_page").value == page


def test_reruns_do_not_retain_notice_frames_in_script_globals(workspace):
    for _ in range(3):
        workspace.run()
    gc.collect()
    script_globals = [
        namespace
        for namespace in gc.get_objects()
        if isinstance(namespace, dict)
        and namespace.get("__name__") == "__main__"
        and str(namespace.get("__file__", "")).endswith("app.py")
    ]
    assert script_globals
    assert all(
        not any(isinstance(value, pd.DataFrame) for value in namespace.values())
        for namespace in script_globals
    )


def test_featured_notice_opens_its_own_dossier(workspace):
    workspace.button(key="inspect_123451-2026").click().run()
    assert not workspace.exception
    assert workspace.radio(key="workspace_page").value == "Dossier"
    assert workspace.selectbox(key="dossier_notice").value == "123451-2026"


def test_empty_filters_can_recover_and_method_remains_available(workspace):
    workspace.text_input(key="filter_query").set_value("NO_SUCH_NOTICE_987654").run()
    assert not workspace.exception
    assert any("No notices match" in warning.value for warning in workspace.warning)
    workspace.radio(key="workspace_page").set_value("Method").run()
    assert not workspace.exception
    assert any("Build the candidate pool" in item.value for item in workspace.markdown)
    workspace.radio(key="workspace_page").set_value("Overview").run()
    next(button for button in workspace.button if button.label == "Reset filters and show notices").click().run()
    assert not workspace.exception
    assert workspace.text_input(key="filter_query").value == ""
    assert len([button for button in workspace.button if button.key and button.key.startswith("inspect_")]) == 3
