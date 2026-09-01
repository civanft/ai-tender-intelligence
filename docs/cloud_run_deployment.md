# Google Cloud Run deployment

The public dashboard runs as a stateless Streamlit container. The application
reads the validated Parquet publication bundled into each image; it does not
write production data to the container filesystem.

## Production target

| Setting | Value |
|---|---|
| Google Cloud project | Local `ATI_GCP_PROJECT` value |
| Cloud Run service | Local `ATI_RUN_SERVICE` value |
| Region | Local `ATI_GCP_REGION` value |
| Billing | Request-based |
| Minimum instances | `0` |
| Maximum instances | `1` |
| Memory | `1 GiB` |
| CPU | `1` |
| Request timeout | `3600 seconds` |
| Public access | Enabled |

The maximum instance limit is a cost guardrail for this portfolio deployment.
Streamlit uses WebSockets, so the 60-minute request timeout is intentional.

## Automatic deployment

`.github/workflows/deploy-cloud-run.yml` deploys a verified `main` revision after
the `Security checks` workflow succeeds. Daily publication-only commits are made
with GitHub's built-in token, which does not emit another ordinary push event;
the refresh workflow therefore dispatches the deploy workflow explicitly after
its own tests and publication commit succeed.

The production path does not store a Google credential in GitHub:

1. GitHub issues a short-lived OIDC token to the deploy job.
2. A Google Workload Identity provider accepts only this repository, the exact
   deploy workflow file, and `refs/heads/main`.
3. The provider impersonates a dedicated deploy service account with no
   user-managed keys.
4. Docker publishes a commit-tagged image to a dedicated Artifact Registry
   repository.
5. The workflow resolves and deploys the image's SHA-256 digest, not its mutable
   tag, then verifies the public service over HTTPS.

Non-secret deployment identifiers are stored as GitHub Repository Variables.
The deploy identity can write only to the production image repository, update
Cloud Run resources, consume project services, and act as the runtime service
account. It cannot impersonate the Cloud Build account. The GitHub `production`
environment accepts deployments only from `main`.

The workflow expects these repository variables; none is a credential:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `CLOUD_RUN_SERVICE`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_RUNTIME_SERVICE_ACCOUNT`

## Manual deployment fallback

Run the following command from the repository root after tests pass:

```bash
export ATI_GCP_PROJECT="your-project-id"
export ATI_GCP_REGION="europe-west1"
export ATI_RUN_SERVICE="ai-tender-intelligence"
export ATI_BUILD_SA="ai-tender-builder@${ATI_GCP_PROJECT}.iam.gserviceaccount.com"
export ATI_RUNTIME_SA="ai-tender-runtime@${ATI_GCP_PROJECT}.iam.gserviceaccount.com"

gcloud run deploy "$ATI_RUN_SERVICE" \
  --project "$ATI_GCP_PROJECT" \
  --region "$ATI_GCP_REGION" \
  --source . \
  --build-service-account "projects/${ATI_GCP_PROJECT}/serviceAccounts/${ATI_BUILD_SA}" \
  --allow-unauthenticated \
  --service-account "$ATI_RUNTIME_SA" \
  --cpu 1 \
  --memory 1Gi \
  --min 0 \
  --max 1 \
  --concurrency 20 \
  --timeout 3600 \
  --port 8080 \
  --execution-environment gen2 \
  --cpu-throttling \
  --no-session-affinity \
  --no-cpu-boost \
  --ingress all \
  --set-env-vars TZ=UTC \
  --labels application=ai-tender-intelligence,environment=production
```

The `.gcloudignore` allowlist prevents local databases, raw TED responses,
virtual environments, caches, Git history, and local secrets from entering the
remote build context.

Project IDs and service-account email addresses are identifiers, not
credentials, but the public runbook uses local variables to avoid publishing
deployment-specific account topology. Never download or commit a service-account
JSON key. Authenticate the CLI with your local Google session; for automated
deployment, prefer short-lived Workload Identity Federation. If the application
later needs a runtime secret, store it in Secret Manager and grant access only to
the runtime service account.

## Data refreshes

The scheduled GitHub Actions workflow refreshes and validates
`data/published/tenders.json` and `data/published/tenders.parquet`, commits a
changed publication, and dispatches the keyless Cloud Run deployment. A failed
test, failed security run, stale commit, failed image push, or unsuccessful
health check stops the workflow and remains visible in GitHub Actions.

## Cost controls

- Keep minimum instances at zero and maximum instances at one.
- Use request-based billing and CPU throttling.
- A project-scoped `100 TRY` monthly alert budget is configured at 50%, 80%,
  and 100% thresholds. This alert-only budget also covers build and storage
  costs; it does not stop usage.
- A separate `100 TRY` monthly spend cap is configured specifically for Cloud
  Run in this project. It sends notifications at 50%, 80%, and 100%, then
  pauses new Cloud Run usage when enforcement is triggered. Enforcement is not
  instantaneous, so small overages remain possible.
- Artifact Registry retains the three newest image versions and removes older
  versions after seven days using `config/artifact_cleanup_policy.json`.
- Review Cloud Run, Cloud Build, and Artifact Registry charges monthly.
