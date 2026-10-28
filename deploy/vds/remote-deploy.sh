#!/usr/bin/env bash
set -Eeuo pipefail

readonly APP_DIR="/opt/ai-tender-intelligence"
readonly COMPOSE_FILE="${APP_DIR}/compose.yaml"
readonly IMAGE_PATTERN='^ghcr\.io/civanft/ai-tender-intelligence@sha256:[0-9a-f]{64}$'
readonly HEALTH_URL="http://127.0.0.1:8501/_stcore/health"
readonly ROLLBACK_TAG="ai-tender-intelligence:rollback"

log() {
  printf '[ati-deploy] %s\n' "$1"
}

fail() {
  printf '[ati-deploy] ERROR: %s\n' "$1" >&2
  exit 1
}

wait_for_health() {
  local _
  for _ in $(seq 1 24); do
    if curl --fail --silent --max-time 5 --output /dev/null "$HEALTH_URL"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

[[ -r "$COMPOSE_FILE" ]] || fail "The production Compose file is missing."

IFS= read -r requested_image || fail "The image reference was not provided."
IFS= read -r ghcr_token || fail "The temporary registry token was not provided."
IFS= read -r ghcr_username || fail "The registry username was not provided."

[[ "$requested_image" =~ $IMAGE_PATTERN ]] || fail "The image reference is not an approved immutable digest."
[[ -n "$ghcr_token" && ${#ghcr_token} -le 512 ]] || fail "The temporary registry token is invalid."
# Scheduled GitHub Actions deployments run as github-actions[bot]. Permit that
# exact service identity without broadening the accepted username alphabet.
[[ "$ghcr_username" =~ ^([A-Za-z0-9-]{1,39}|github-actions\[bot\])$ ]] || fail "The registry username is invalid."

exec 9>"${APP_DIR}/deploy.lock"
flock -n 9 || fail "Another deployment is already running."

docker_config="$(mktemp -d /tmp/ati-docker-config.XXXXXX)"
cleanup() {
  unset ghcr_token
  unset ghcr_username
  rm -rf -- "$docker_config"
}
trap cleanup EXIT

printf '%s' "$ghcr_token" | docker --config "$docker_config" login ghcr.io \
  --username "$ghcr_username" --password-stdin >/dev/null
unset ghcr_token
unset ghcr_username

cd "$APP_DIR"
previous_container="$(docker ps --quiet \
  --filter 'label=com.docker.compose.project=ai-tender-intelligence' \
  --filter 'label=com.docker.compose.service=app' | head -1)"
previous_image=""
previous_image_id=""
if [[ -n "$previous_container" ]]; then
  previous_image="$(docker inspect --format '{{.Config.Image}}' "$previous_container")"
  previous_image_id="$(docker inspect --format '{{.Image}}' "$previous_container")"
fi

export ATI_IMAGE="$requested_image"
log "Pulling the verified image digest."
docker --config "$docker_config" compose --file "$COMPOSE_FILE" pull app
docker compose --file "$COMPOSE_FILE" up --detach --remove-orphans app

if ! wait_for_health; then
  log "The new container failed its health check."
  if [[ -n "$previous_image" ]]; then
    log "Restoring the previous image."
    export ATI_IMAGE="$previous_image"
    docker compose --file "$COMPOSE_FILE" up --detach --remove-orphans app
    if wait_for_health; then
      fail "Deployment failed; the previous healthy image was restored."
    fi
    fail "Deployment and automatic rollback both failed."
  fi
  docker compose --file "$COMPOSE_FILE" stop app
  fail "The first deployment failed and its unhealthy container was stopped."
fi

if [[ -n "$previous_image_id" ]]; then
  docker image tag "$previous_image_id" "$ROLLBACK_TAG"
fi
docker image prune --force >/dev/null

log "Deployment is healthy."
