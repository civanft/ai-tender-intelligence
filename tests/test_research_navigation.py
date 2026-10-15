from datetime import datetime, timezone
from pathlib import Path

from test_workspace_navigation import workspace


def test_research_destinations_and_tools_render(workspace):
    workspace.radio(key="workspace_page").set_value("Research desk").run()
    assert not workspace.exception
    for tool in ("Compare", "Deadline radar", "Fit lab", "Watchlist"):
        workspace.radio(key="research_tool").set_value(tool).run()
        assert not workspace.exception, tool
    workspace.radio(key="workspace_page").set_value("Buyers").run()
    assert not workspace.exception


def test_save_notice_compare_and_session_isolation(workspace):
    workspace.button(key="inspect_123451-2026").click().run()
    workspace.button(key="research_save_dossier").click().run()
    assert not workspace.exception
    assert "123451-2026" in workspace.session_state["research_workspace"]["saved"]
    workspace.button(key="research_dossier_desk").click().run()
    assert not workspace.exception
    workspace.multiselect(key="research_add_selection").set_value(["123450-2026"]).run()
    workspace.button(key="research_add").click().run()
    workspace.radio(key="research_tool").set_value("Compare").run()
    assert not workspace.exception
    assert len(workspace.multiselect(key="research_compare").value) == 2
    from streamlit.testing.v1 import AppTest
    other = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not other.exception
    assert other.session_state["research_workspace"]["saved"] == {}


def test_saved_search_restores_filters_and_desk_survives_empty_filters(workspace):
    workspace.text_input(key="filter_query").set_value("Data").run()
    workspace.text_input(key="research_view_name").set_value("My data view").run()
    next(b for b in workspace.button if b.label == "Save current search").click().run()
    workspace.text_input(key="filter_query").set_value("NO_SUCH_NOTICE").run()
    workspace.radio(key="workspace_page").set_value("Research desk").run()
    assert not workspace.exception
    next(b for b in workspace.button if b.label == "Apply saved search").click().run()
    assert not workspace.exception
    assert workspace.text_input(key="filter_query").value == "Data"


def test_saved_dossier_routing_survives_filters(workspace):
    workspace.button(key="inspect_123451-2026").click().run()
    workspace.button(key="research_save_dossier").click().run()
    workspace.button(key="research_dossier_desk").click().run()
    workspace.text_input(key="filter_query").set_value("NO_SUCH_NOTICE").run()
    workspace.button(key="research_open_123451-2026").click().run()
    assert not workspace.exception
    assert workspace.selectbox(key="dossier_notice").value == "123451-2026"


def test_research_note_checks_and_stage_survive_navigation(workspace):
    workspace.button(key="inspect_123451-2026").click().run()
    workspace.button(key="research_save_dossier").click().run()
    workspace.button(key="research_dossier_desk").click().run()
    workspace.selectbox(key="research_edit_stage_123451-2026").set_value("Researching")
    workspace.text_area(key="research_edit_note_123451-2026").set_value("Check delivery language")
    workspace.checkbox(key="research_edit_check_123451-2026_scope").set_value(True)
    next(b for b in workspace.button if b.label == "Save research").click().run()
    assert not workspace.exception
    entry = workspace.session_state["research_workspace"]["saved"]["123451-2026"]
    assert entry["stage"] == "Researching"
    assert entry["note"] == "Check delivery language"
    assert entry["checks"]["scope"] is True
    workspace.radio(key="workspace_page").set_value("Overview").run()
    workspace.radio(key="workspace_page").set_value("Research desk").run()
    assert workspace.text_area(key="research_edit_note_123451-2026").value == "Check delivery language"


def test_fit_lab_live_ranking_changes_with_user_weights(workspace, monkeypatch):
    from tender_intelligence import research_ui
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2026, 9, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(research_ui, "datetime", Clock)
    workspace.radio(key="workspace_page").set_value("Research desk").run()
    workspace.radio(key="research_tool").set_value("Fit lab").run()
    assert not workspace.exception
    before = workspace.dataframe[0].value["Scenario fit / 100"].tolist()
    workspace.slider(key="research_weight_market").set_value(100)
    for name in ("theme", "evidence", "runway", "budget"):
        workspace.slider(key="research_weight_" + name).set_value(0)
    workspace.run()
    assert not workspace.exception
    after = workspace.dataframe[0].value["Scenario fit / 100"].tolist()
    assert after == [100, 100, 100]
    assert before != after
