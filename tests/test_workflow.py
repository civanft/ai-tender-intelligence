import re
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/update-tenders.yml"
SECURITY_WORKFLOW = WORKFLOW.with_name("security.yml")
DEPLOY_WORKFLOW = WORKFLOW.with_name("deploy-cloud-run.yml")
VDS_DEPLOY_WORKFLOW = WORKFLOW.with_name("deploy-vds.yml")
DEPENDABOT = WORKFLOW.parents[1] / "dependabot.yml"


def test_refresh_workflow_is_scheduled_manual_and_commits_publications():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert "schedule:" in source
    assert "timezone: Europe/Istanbul" in source
    assert "contents: write" in source
    assert "pytest" in source
    assert "python scripts/fetch_tenders.py --scope ACTIVE --page-size 250" in source
    assert "for publication in data/published/tenders.json data/published/tenders.json.gz data/published/tenders.parquet" in source
    assert 'git add -- "$publication"' in source
    assert "gh workflow run deploy-cloud-run.yml --ref main" in source
    assert "actions: write" in source


def test_actions_are_sha_pinned_and_write_permission_is_isolated():
    sources = [
        WORKFLOW.read_text(encoding="utf-8"),
        SECURITY_WORKFLOW.read_text(encoding="utf-8"),
        DEPLOY_WORKFLOW.read_text(encoding="utf-8"),
        VDS_DEPLOY_WORKFLOW.read_text(encoding="utf-8"),
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


def test_cloud_run_deploy_is_keyless_gated_and_digest_pinned():
    source = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert 'workflows: ["Security checks"]' in source
    assert "github.event.workflow_run.conclusion == 'success'" in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.head_branch == 'main'" in source
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in source
    assert "environment: production" in source
    assert "id-token: write" in source
    assert "google-github-actions/auth@" in source
    assert "workload_identity_provider:" in source
    assert "service_account:" in source
    assert "credentials_json" not in source
    assert "docker build --pull" in source
    assert "docker push" in source
    assert "image_summary.digest" in source
    assert '--image "${{ steps.image.outputs.reference }}"' in source
    assert "--allow-unauthenticated" not in source
    assert "steps.revision.outputs.current == 'true'" in source


def test_vds_deploy_is_disabled_by_default_restricted_and_digest_pinned():
    source = VDS_DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "vars.VDS_DEPLOY_ENABLED == 'true'" in source
    assert 'workflows: ["Security checks"]' in source
    assert "github.event.workflow_run.conclusion == 'success'" in source
    assert "environment: production" in source
    assert "packages: write" in source
    assert "VDS_SSH_PRIVATE_KEY: ${{ secrets.VDS_SSH_PRIVATE_KEY }}" in source
    assert "StrictHostKeyChecking=yes" in source
    assert "ssh-keyscan" not in source
    assert "@${digest}" in source
    assert "steps.revision.outputs.current == 'true'" in source


def test_refresh_can_dispatch_vds_without_disabling_cloud_run_early():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "vars.VDS_DEPLOY_ENABLED == 'true'" in source
    assert "gh workflow run deploy-vds.yml --ref main" in source
    assert "vars.CLOUD_RUN_DEPLOY_ENABLED != 'false'" in source


def test_security_automation_covers_dependencies_code_and_updates():
    security_source = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    dependabot_source = DEPENDABOT.read_text(encoding="utf-8")

    assert "python -m pip_audit" in security_source
    assert "python -m bandit" in security_source
    assert "github/codeql-action/init@" in security_source
    assert "package-ecosystem: pip" in dependabot_source
    assert "package-ecosystem: github-actions" in dependabot_source
