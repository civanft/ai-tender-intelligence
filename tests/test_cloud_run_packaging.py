import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_container_runs_as_non_root_and_uses_cloud_run_port() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim-bookworm@sha256:" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert '"--server.port=8080"' in dockerfile
    assert "--require-hashes" in dockerfile
    assert "--only-binary=:all:" in dockerfile


def test_build_context_excludes_local_state_and_secrets() -> None:
    required_secret_denies = {
        ".streamlit/secrets.toml",
        "**/secrets.toml",
        "**/.env.*",
        "**/*.pem",
        "**/*.key",
        "**/*credential*.json",
        "**/*service-account*.json",
        "**/*service_account*.json",
        "**/application_default_credentials.json",
    }
    for ignore_name in (".dockerignore", ".gcloudignore"):
        rules = (ROOT / ignore_name).read_text(encoding="utf-8").splitlines()
        assert rules[0] == "*"
        assert "!data/published/tenders.parquet" in rules
        assert "!data/processed/" not in rules
        assert "!config/**" not in rules
        assert "config/*" in rules
        assert "!config/profile.json" in rules
        assert "!config/taxonomy.json" in rules
        assert "!.env" not in rules
        assert "!.git/" not in rules
        assert required_secret_denies.issubset(rules)


def test_artifact_cleanup_keeps_safe_rollback_versions() -> None:
    policy_path = ROOT / "config" / "artifact_cleanup_policy.json"
    policies = json.loads(policy_path.read_text(encoding="utf-8"))
    policies_by_name = {policy["name"]: policy for policy in policies}

    delete_policy = policies_by_name["delete-old-images"]
    assert delete_policy["action"] == {"type": "Delete"}
    assert delete_policy["condition"] == {
        "tagState": "any",
        "olderThan": "7d",
    }

    keep_policy = policies_by_name["keep-recent-images"]
    assert keep_policy["action"] == {"type": "Keep"}
    assert keep_policy["mostRecentVersions"]["keepCount"] == 3
