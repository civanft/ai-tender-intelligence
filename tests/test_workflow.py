from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/update-tenders.yml"


def test_refresh_workflow_is_scheduled_manual_and_commits_publications():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert "schedule:" in source
    assert "timezone: Europe/Istanbul" in source
    assert "contents: write" in source
    assert "pytest" in source
    assert "python scripts/fetch_tenders.py --scope ACTIVE --page-size 250" in source
    assert "git add -- data/published/tenders.json data/published/tenders.parquet" in source
