from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VDS_DIR = ROOT / "deploy" / "vds"


def test_vds_compose_exposes_only_loopback_and_limits_the_container() -> None:
    source = (VDS_DIR / "compose.yaml").read_text(encoding="utf-8")

    assert "127.0.0.1:8501:8080" in source
    assert "0.0.0.0" not in source
    assert "read_only: true" in source
    assert "no-new-privileges:true" in source
    assert "cap_drop:" in source and "- ALL" in source
    assert "mem_limit: 2g" in source
    assert "cpus: 1.0" in source
    assert "COPY static/ ./static/" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "/_stcore/health" in source
    assert "max-size: \"10m\"" in source


def test_remote_deploy_accepts_only_this_repositorys_immutable_digest() -> None:
    source = (VDS_DIR / "remote-deploy.sh").read_text(encoding="utf-8")

    assert "ghcr\\.io/civanft/ai-tender-intelligence@sha256:" in source
    assert "docker compose" in source
    assert "docker image prune --force" in source
    assert "Restoring the previous image" in source
    assert "rm -rf -- \"$docker_config\"" in source
    assert "github-actions\\[bot\\]" in source
    assert "eval " not in source


def test_nginx_proxy_supports_websockets_and_security_headers() -> None:
    source = (VDS_DIR / "nginx-site.conf.template").read_text(encoding="utf-8")

    assert "proxy_set_header Upgrade $http_upgrade;" in source
    assert "proxy_read_timeout 3600s;" in source
    assert 'X-Content-Type-Options "nosniff"' in source
    assert 'X-Frame-Options "DENY"' in source
    assert "client_max_body_size 1m;" in source
    assert "proxy_pass http://127.0.0.1:8501;" in source


def test_server_installer_restricts_the_automation_key() -> None:
    source = (VDS_DIR / "install-server.sh").read_text(encoding="utf-8")
    hardening = (VDS_DIR / "harden-ssh.sh").read_text(encoding="utf-8")

    assert 'command=\\"/usr/local/sbin/ati-remote-deploy\\",restrict' in source
    assert "ufw default deny incoming" in source
    assert "passwd --lock" in source
    assert "chmod 0600" in source
    assert "certbot --nginx" in source
    assert "PermitRootLogin no" in hardening
    assert "PasswordAuthentication no" in hardening
    assert "AllowUsers ${ADMIN_USER} ${DEPLOY_USER}" in hardening
    assert "sshd -t" in hardening


def test_documented_private_key_names_are_git_ignored() -> None:
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "ati_admin" in ignore_rules
    assert "ati_github_deploy" in ignore_rules
