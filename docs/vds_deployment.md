# Büyükweb VDS deployment

This deployment keeps the public Streamlit application inside a locked-down
Docker container and exposes only Nginx on ports 80 and 443. The application
port is bound to `127.0.0.1`, so it cannot be reached directly from the
internet. Nginx supports Streamlit WebSockets and obtains HTTPS certificates
through Certbot.

The existing Cloud Run deployment should remain enabled until the VDS URL has
passed the production checks in this guide.

## Prepared production structure

| Component | Purpose |
|---|---|
| `deploy/vds/compose.yaml` | Resource-limited, read-only application container |
| `deploy/vds/nginx-site.conf.template` | WebSocket proxy, request limits, and response security headers |
| `deploy/vds/install-server.sh` | Repeatable Ubuntu 24.04 server preparation |
| `deploy/vds/harden-ssh.sh` | Post-login-check removal of root and password SSH access |
| `deploy/vds/remote-deploy.sh` | Digest-only deployment, health check, and automatic rollback |
| `.github/workflows/deploy-vds.yml` | Build on GitHub, publish to GHCR, and deploy with a restricted SSH key |

The EU-27 application container is limited to one CPU and 2 GiB RAM. On the 2-core,
4-GB VDS 2 this leaves room for Nginx, the operating system, and a second small
project. Each later project should use a different loopback port and a separate
Nginx site file.

## One-time server preparation

Select **Ubuntu 24.04 LTS** when ordering the VDS. Do not purchase a web control
panel or Windows licence. Before setup, point a domain or subdomain to the
server's IPv4 address with an `A` DNS record.

Generate two different SSH keys locally: one for normal server administration
and one for GitHub's restricted deployment command.

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/ati_admin -C "ai-tender-admin"
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/ati_github_deploy -C "ai-tender-deploy"
```

Copy the repository and both **public** `.pub` files to the new server, then run:

```bash
sudo ./deploy/vds/install-server.sh \
  --domain tendermeridian.com \
  --email owner@example.com \
  --admin-public-key /root/ati_admin.pub \
  --deploy-public-key /root/ati_github_deploy.pub
```

The installer creates password-locked `ati-admin` and `ati-deploy` accounts.
The deployment key is restricted by OpenSSH to the root-owned deployment
program: it cannot open a shell, forward ports, or execute an arbitrary command.
The program accepts only an immutable image digest belonging to this repository.

Keep the original setup session open. In a second terminal, confirm the
administrator key works:

```bash
ssh -i ~/.ssh/ati_admin ati-admin@SERVER_IP
```

Only after that login succeeds, disable remote root and password authentication:

```bash
sudo ./deploy/vds/harden-ssh.sh
```

Open one more new `ati-admin` session before closing the original root session.
This two-stage process prevents an accidental server lockout.

Before trusting the server from GitHub Actions, obtain its SSH host key through
the provider console and verify its fingerprint out of band. Do not rely on an
unverified `ssh-keyscan` result.

## GitHub configuration

Create the following **Repository variables**:

| Variable | Example |
|---|---|
| `VDS_DEPLOY_ENABLED` | `true` only after server preparation |
| `VDS_HOST` | Server IPv4 address or deployment hostname |
| `VDS_SSH_PORT` | `22` |
| `VDS_SSH_USER` | `ati-deploy` |
| `VDS_SSH_KNOWN_HOSTS` | Verified complete OpenSSH known-hosts line |
| `VDS_SITE_URL` | `https://tendermeridian.com` |

Create one encrypted **Repository secret**:

| Secret | Value |
|---|---|
| `VDS_SSH_PRIVATE_KEY` | Full contents of `~/.ssh/ati_github_deploy` |

Never commit the private key, a server password, a GitHub token, or a `.env`
file. The workflow uses GitHub's short-lived token for GHCR; the VDS stores the
token only in a temporary directory for the duration of the image pull.

## HTTPS and first deployment

After DNS resolves to the server, enable HTTPS before the first automated
deployment. Certbot's challenge can complete while the upstream app is still
offline:

```bash
sudo certbot --nginx --non-interactive --agree-tos --redirect \
  --domain tendermeridian.com --domain www.tendermeridian.com \
  --email owner@example.com
```

Run **Actions → Deploy VDS → Run workflow**. The workflow builds the same locked
Dockerfile used by Cloud Run, pushes a commit-tagged image, resolves its SHA-256
digest, and sends the digest, authenticated GitHub username, and a temporary
registry token to the restricted deployment account.

Verify certificate renewal without changing the certificate:

```bash
sudo certbot renew --dry-run
```

## Production checks

```bash
curl --fail --show-error --silent https://tendermeridian.com/_stcore/health
sudo docker compose -f /opt/ai-tender-intelligence/compose.yaml ps
sudo nginx -t
sudo ufw status verbose
```

Also open the dashboard on desktop and mobile, change every filter, open a TED
notice link, and leave a session open for several minutes to confirm the
WebSocket remains connected.

Only after these checks succeed should Cloud Run be disabled. Set the repository
variable `CLOUD_RUN_DEPLOY_ENABLED` to `false`; its workflow is intentionally
left available as a rollback route during migration.

## Updates and rollback

When `VDS_DEPLOY_ENABLED=true`, a successful security check on a new `main`
commit deploys the same exact revision automatically. The daily TED refresh also
dispatches the VDS workflow after its own tests pass.

The server checks `/_stcore/health` for up to two minutes. If a new image does
not become healthy, it restores the previous image. It retains the immediately
previous image under a local rollback tag and removes only untagged images; it
does not prune images belonging to future projects.

## Adding a second project

Give the second project's container another loopback port, for example
`127.0.0.1:8502`, and add another Nginx server block for its domain. Do not bind
application containers to `0.0.0.0`; only ports 22, 80, and 443 should be public.
