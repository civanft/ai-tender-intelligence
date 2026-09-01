import re
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/update-tenders.yml"
SECURITY_WORKFLOW = WORKFLOW.with_name("security.yml")
DEPENDABOT = WORKFLOW.parents[1] / "dependabot.yml"


def test_refresh_workflow_is_scheduled_manual_and_commits_publications():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert "schedule:" in source
    assert "timezone: Europe/Istanbul" in source
    assert "contents: write" in source
    assert "pytest" in source
    assert "python scripts/fetch_tenders.py --scope ACTIVE --page-size 250" in source
    assert "git add -- data/published/tenders.json data/published/tenders.parquet" in source


def test_actions_are_sha_pinned_and_write_permission_is_isolated():
    sources = [
        WORKFLOW.read_text(encoding="utf-8"),
        SECURITY_WORKFLOW.read_text(encoding="utf-8"),
    ]
    action_reference = re.compile(r"^\s*uses:\s*[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)

    for source in sources:
        uses_lines = [line for line in source.splitlines() if line.strip().startswith("uses:")]
        assert uses_lines
        assert len(action_reference.findall(source)) == len(uses_lines)

    refresh_source = sources[0]
    assert "permissions:\n  contents: read" in refresh_source
    assert "publish:\n    needs: refresh" in refresh_source
    assert "contents: write" in refresh_source
    assert "--require-hashes --only-binary=:all:" in refresh_source


def test_security_automation_covers_dependencies_code_and_updates():
    security_source = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    dependabot_source = DEPENDABOT.read_text(encoding="utf-8")

    assert "python -m pip_audit" in security_source
    assert "python -m bandit" in security_source
    assert "github/codeql-action/init@" in security_source
    assert "package-ecosystem: pip" in dependabot_source
    assert "package-ecosystem: github-actions" in dependabot_source
