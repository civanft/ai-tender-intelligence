# Tender Meridian — release security check

Checked on 2026-10-14 (Europe/Istanbul). This records observed results, not a
guarantee that every possible vulnerability is absent.

## Product name

The interface, page title, logo alternative text, empty state, CSV download name,
calendar producer, HTML briefs, README, design documents, Python distribution and
container title now use **Tender Meridian**. The logo artwork is unchanged.
Existing GitHub/GHCR URLs, server/Compose identifiers, Python import paths and
calendar event UIDs are retained for compatibility. Renaming those infrastructure
identifiers requires a coordinated migration of the running deployment.

## Repository and dependencies

- Gitleaks scanned all 63 fetched commits with full history and all refs: no findings.
- Gitleaks scanned the current publication candidate, including non-ignored new
  files: no findings. No credential values were printed.
- Historical filenames contained no forbidden credential/local-state paths.
- The publication guard now includes untracked files and inspects gzip contents
  with a 256 MiB decompression limit. Private workspace JSON, SSH directories,
  raw data and databases are blocked from publication.
- Eight representative secret/local-state paths were verified as Git-ignored.
- Three known advisories affected urllib3 2.7.0. Both hashed requirements files
  and uv.lock now resolve urllib3 2.8.0. Both requirements audits report no known
  vulnerabilities after the update.
- 100 application tests and five publication-guard tests passed. Bandit,
  actionlint, shellcheck and Git whitespace checks passed.
- GitHub secret scanning, push protection and Dependabot security updates are
  enabled. The open secret-scanning alert list was empty. GitHub still has nine
  urllib3 dependency alerts across manifests until the fixed files are published
  and GitHub re-evaluates them.

No push, repository rename or production deployment was performed by this review.

## Network and firewall observations

- The local app listens only on 127.0.0.1:8501.
- A foreign-origin WebSocket handshake was rejected with HTTP 403. Requests for
  /.env, /.git/config, /.streamlit/secrets.toml and the SQLite path returned the
  HTML application fallback, not the requested files. Streamlit's fallback uses
  HTTP 200; the deployment's Nginx hidden-path rule provides an explicit 404.
- macOS Application Firewall is disabled and stealth mode is off. These machine
  settings were inspected but not changed by a project firewall test.
- The previously supplied VDS address had TCP 8501 open. Its HTTP response
  identified WebSockify and its Streamlit health endpoint returned 404; this is
  not a verified instance of this application.
- SSH (22), HTTP (80), HTTPS (443) and MySQL (3306) timed out from this network.
  Docker (2375/2376), PostgreSQL (5432), Redis (6379) and port 8080 were refused.
  A timeout alone does not prove a working firewall.
- The previously supplied domain returned NXDOMAIN, including from the 1.1.1.1
  resolver. No live HTTPS application or certificate could be verified.
- Remote UFW rules, SSH effective settings, listeners, Fail2ban and Docker
  bindings could not be inspected because authenticated SSH access was unavailable.

## Deployment fixes prepared locally

The SSH hardening drop-in now precedes cloud-init's usual 50-* file. Before
reloading SSH it checks effective configuration and refuses to claim success if
root/password/keyboard-interactive login is still enabled. Nginx explicitly
rejects hidden paths while preserving /.well-known/ for certificate challenges.
The existing Compose file binds the app to loopback and restricts its capabilities,
filesystem, privileges and resources. These are repository settings; they have
not been confirmed or applied on the remote machine.

The remaining production check requires the current VDS address, SSH port and
administrator access. Do not send passwords or private keys in chat. Verify the
machine identity before altering the service found on port 8501.
