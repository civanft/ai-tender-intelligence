#!/usr/bin/env bash
set -Eeuo pipefail

readonly ADMIN_USER="ati-admin"
readonly DEPLOY_USER="ati-deploy"
readonly SSHD_DROP_IN="/etc/ssh/sshd_config.d/90-ai-tender-intelligence.conf"

[[ $EUID -eq 0 ]] || { echo "Run this hardening step as root." >&2; exit 1; }

for account in "$ADMIN_USER" "$DEPLOY_USER"; do
  account_home="$(getent passwd "$account" | cut -d: -f6)"
  authorized_keys="${account_home}/.ssh/authorized_keys"
  [[ -s "$authorized_keys" && ! -L "$authorized_keys" ]] || {
    echo "A regular authorized_keys file is required for ${account}." >&2
    exit 1
  }
  [[ "$(stat -c '%U:%G:%a' "$authorized_keys")" == "${account}:${account}:600" ]] || {
    echo "Unsafe ownership or permissions on ${authorized_keys}." >&2
    exit 1
  }
done

cat > "$SSHD_DROP_IN" <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
X11Forwarding no
AllowUsers ${ADMIN_USER} ${DEPLOY_USER}
EOF
chmod 0644 "$SSHD_DROP_IN"
sshd -t
systemctl reload ssh

echo "SSH hardening is active. Keep the current session open until a new ati-admin login succeeds."
