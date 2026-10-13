#!/usr/bin/env bash
set -Eeuo pipefail

readonly DEPLOY_USER="ati-deploy"
readonly ADMIN_USER="ati-admin"
readonly APP_DIR="/opt/ai-tender-intelligence"

domain=""
email=""
admin_public_key_file=""
deploy_public_key_file=""
ssh_port="22"

usage() {
  cat <<'EOF'
Usage: sudo ./deploy/vds/install-server.sh \
  --domain tenders.example.com \
  --email owner@example.com \
  --admin-public-key /root/ati_admin.pub \
  --deploy-public-key /root/ati_deploy.pub \
  [--ssh-port 22]

The domain must already point to this server before the optional TLS command is run.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) domain="${2:-}"; shift 2 ;;
    --email) email="${2:-}"; shift 2 ;;
    --admin-public-key) admin_public_key_file="${2:-}"; shift 2 ;;
    --deploy-public-key) deploy_public_key_file="${2:-}"; shift 2 ;;
    --ssh-port) ssh_port="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "Run this installer as root." >&2; exit 1; }
[[ "$domain" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$ ]] || {
  echo "Provide a valid fully qualified domain name." >&2; exit 1;
}
[[ "$email" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || {
  echo "Provide a valid certificate contact email." >&2; exit 1;
}
if [[ ! "$ssh_port" =~ ^[0-9]{1,5}$ ]] || (( ssh_port < 1 || ssh_port > 65535 )); then
  echo "Provide a valid SSH port." >&2; exit 1;
fi
read_ed25519_public_key() {
  local key_file="$1"
  local key_purpose="$2"
  local public_key

  [[ -f "$key_file" && ! -L "$key_file" ]] || {
    echo "The ${key_purpose} public-key file is missing or is a symbolic link." >&2
    return 1
  }
  [[ "$(wc -l < "$key_file")" -eq 1 ]] || {
    echo "The ${key_purpose} public-key file must contain exactly one line." >&2
    return 1
  }
  public_key="$(<"$key_file")"
  [[ "$public_key" =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ .*)?$ ]] || {
    echo "Use a dedicated Ed25519 key for ${key_purpose}." >&2
    return 1
  }
  ssh-keygen -l -f "$key_file" >/dev/null || {
    echo "The ${key_purpose} public key is malformed." >&2
    return 1
  }
  printf '%s' "$public_key"
}

admin_public_key="$(read_ed25519_public_key "$admin_public_key_file" administration)"
deploy_public_key="$(read_ed25519_public_key "$deploy_public_key_file" deployment)"
[[ "$admin_public_key" != "$deploy_public_key" ]] || {
  echo "Administration and deployment must use different SSH keys." >&2; exit 1;
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
[[ -f "$repo_root/deploy/vds/compose.yaml" && -f "$repo_root/deploy/vds/remote-deploy.sh" ]] || {
  echo "Run the installer from a complete project checkout." >&2; exit 1;
}

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes --no-install-recommends \
  ca-certificates curl docker.io docker-compose-v2 fail2ban nginx \
  certbot python3-certbot-nginx unattended-upgrades ufw

systemctl enable --now docker nginx fail2ban unattended-upgrades

if ! id "$ADMIN_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$ADMIN_USER"
fi
passwd --lock "$ADMIN_USER" >/dev/null
usermod --append --groups sudo "$ADMIN_USER"

admin_home="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"
install -d -m 0700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$admin_home/.ssh"
printf '%s\n' "no-agent-forwarding,no-port-forwarding,no-X11-forwarding ${admin_public_key}" \
  > "$admin_home/.ssh/authorized_keys"
chown "$ADMIN_USER:$ADMIN_USER" "$admin_home/.ssh/authorized_keys"
chmod 0600 "$admin_home/.ssh/authorized_keys"
printf '%s ALL=(ALL:ALL) NOPASSWD:ALL\n' "$ADMIN_USER" > /etc/sudoers.d/90-ati-admin
chmod 0440 /etc/sudoers.d/90-ati-admin
visudo --check >/dev/null

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi
passwd --lock "$DEPLOY_USER" >/dev/null
usermod --append --groups docker "$DEPLOY_USER"

install -d -m 0755 -o root -g root "$APP_DIR"
install -m 0644 -o root -g root "$repo_root/deploy/vds/compose.yaml" "$APP_DIR/compose.yaml"
install -m 0755 -o root -g root "$repo_root/deploy/vds/remote-deploy.sh" /usr/local/sbin/ati-remote-deploy
touch "$APP_DIR/deploy.lock"
chown "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR/deploy.lock"
chmod 0600 "$APP_DIR/deploy.lock"

deploy_home="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
install -d -m 0700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$deploy_home/.ssh"
authorized_key="command=\"/usr/local/sbin/ati-remote-deploy\",restrict ${deploy_public_key}"
printf '%s\n' "$authorized_key" > "$deploy_home/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "$deploy_home/.ssh/authorized_keys"
chmod 0600 "$deploy_home/.ssh/authorized_keys"

sed "s/__SITE_DOMAIN__/${domain}/g" "$repo_root/deploy/vds/nginx-site.conf.template" \
  > /etc/nginx/sites-available/ai-tender-intelligence.conf
ln -sfn /etc/nginx/sites-available/ai-tender-intelligence.conf \
  /etc/nginx/sites-enabled/ai-tender-intelligence.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

ufw default deny incoming
ufw default allow outgoing
ufw allow "${ssh_port}/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

if ! swapon --show=NAME --noheadings | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 0600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

cat > /etc/sysctl.d/99-ai-tender-intelligence.conf <<'EOF'
vm.swappiness=10
EOF
sysctl --system >/dev/null

cat <<EOF
Server preparation is complete.

Next steps:
1. In a second terminal, verify the administrator key can log in as ${ADMIN_USER}.
2. Keep this session open and run deploy/vds/harden-ssh.sh to disable root/password login.
3. Confirm that DNS points to this server, then enable HTTPS with:
   sudo certbot --nginx --non-interactive --agree-tos --redirect \\
     --domain ${domain} --email ${email}
4. Add the VDS repository variables and secret described in docs/vds_deployment.md.
5. Run the GitHub Actions workflow "Deploy VDS" once.
EOF
