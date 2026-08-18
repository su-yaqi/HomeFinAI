#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

readonly COMPOSE_FILES=(
  --file compose.yml
  --file compose.intranet.yml
  --file compose.release.yml
)

log() {
  printf '[homefin-deploy] %s\n' "$*"
}

fail() {
  printf '[homefin-deploy] ERROR: %s\n' "$*" >&2
  exit 1
}

require_variable() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    fail "Required variable is missing: ${name}"
  fi
}

validate_digest_reference() {
  local name="$1"
  local value="${!name}"
  if [[ ! "${value}" =~ ^[a-z0-9.-]+(:[0-9]+)?/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]; then
    fail "${name} must be a lowercase registry image reference pinned by sha256 digest"
  fi
}

validate_absolute_directory() {
  local name="$1"
  local value="${!name}"
  if [[ "${value}" != /* || "${value}" == "/" ]]; then
    fail "${name} must be an absolute directory other than /"
  fi
}

compose() {
  docker compose \
    "${COMPOSE_FILES[@]}" \
    --project-name "${STACK_NAME}" \
    "$@"
}

compose_with_images() {
  local backend_image="$1"
  local frontend_image="$2"
  shift 2
  HOMEFIN_BACKEND_IMAGE="${backend_image}" \
    HOMEFIN_FRONTEND_IMAGE="${frontend_image}" \
    compose "$@"
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempts="${HEALTHCHECK_ATTEMPTS:-30}"
  local interval="${HEALTHCHECK_INTERVAL_SECONDS:-5}"
  local attempt

  for ((attempt = 1; attempt <= attempts; attempt += 1)); do
    if curl --fail --silent --show-error --max-time 10 "${url}" >/dev/null; then
      log "${label} health check passed: ${url}"
      return 0
    fi
    if ((attempt < attempts)); then
      sleep "${interval}"
    fi
  done

  log "${label} health check failed after ${attempts} attempts: ${url}"
  return 1
}

state_value() {
  local key="$1"
  local file="$2"
  awk -F '\t' -v wanted="${key}" '$1 == wanted {print $2; exit}' "${file}"
}

write_state() {
  local temporary_state
  temporary_state="$(mktemp "${HOMEFIN_DEPLOY_STATE_DIR}/current.XXXXXX")"
  {
    printf 'DEPLOY_SHA\t%s\n' "${DEPLOY_SHA}"
    printf 'HOMEFIN_BACKEND_IMAGE\t%s\n' "${HOMEFIN_BACKEND_IMAGE}"
    printf 'HOMEFIN_FRONTEND_IMAGE\t%s\n' "${HOMEFIN_FRONTEND_IMAGE}"
    printf 'DEPLOYED_AT_UTC\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } >"${temporary_state}"
  mv "${temporary_state}" "${CURRENT_STATE}"
}

create_database_backup() {
  local timestamp backup_file temporary_backup
  timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
  backup_file="${HOMEFIN_BACKUP_DIR}/${STACK_NAME}-${DEPLOY_SHA}-${timestamp}.dump"
  temporary_backup="${backup_file}.tmp"

  log "Creating pre-migration PostgreSQL backup"
  # Expansion happens inside the database container, using its existing environment.
  # shellcheck disable=SC2016
  if ! compose exec -T db sh -c \
    'PGPASSWORD="$POSTGRES_PASSWORD" exec pg_dump --host 127.0.0.1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format custom' \
    >"${temporary_backup}"; then
    rm -f "${temporary_backup}"
    fail "Pre-migration backup command failed"
  fi

  if [[ ! -s "${temporary_backup}" ]]; then
    rm -f "${temporary_backup}"
    fail "Pre-migration backup is empty: ${temporary_backup}"
  fi
  mv "${temporary_backup}" "${backup_file}"
  log "Pre-migration backup verified: ${backup_file}"
}

rollback_images() {
  local previous_backend="$1"
  local previous_frontend="$2"

  validate_digest_value "${previous_backend}" "previous backend image"
  validate_digest_value "${previous_frontend}" "previous frontend image"

  log "Attempting image-only rollback; the database schema will not be downgraded"
  compose_with_images "${previous_backend}" "${previous_frontend}" \
    pull --policy always backend frontend || return 1
  compose_with_images "${previous_backend}" "${previous_frontend}" \
    up --detach --no-build --wait backend frontend db-backup || return 1

  wait_for_url "Backend rollback" "${BACKEND_URL}/api/v1/utils/health-check/" &&
    wait_for_url "Frontend rollback" "${FRONTEND_URL}/" &&
    wait_for_url "Frontend API proxy rollback" "${FRONTEND_URL}/api/v1/utils/health-check/"
}

validate_digest_value() {
  local value="$1"
  local label="$2"
  if [[ ! "${value}" =~ ^[a-z0-9.-]+(:[0-9]+)?/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]; then
    fail "Invalid ${label} in deployment state"
  fi
}

for variable in \
  STACK_NAME \
  DEPLOY_SHA \
  HOMEFIN_BACKEND_IMAGE \
  HOMEFIN_FRONTEND_IMAGE \
  HOMEFIN_BACKUP_DIR \
  HOMEFIN_DEPLOY_STATE_DIR \
  BACKEND_URL \
  FRONTEND_URL \
  SECRET_KEY \
  FIRST_SUPERUSER \
  FIRST_SUPERUSER_PASSWORD \
  POSTGRES_PASSWORD \
  POSTGRES_USER \
  POSTGRES_DB \
  FRONTEND_HOST \
  BACKEND_CORS_ORIGINS; do
  require_variable "${variable}"
done

if [[ ! "${STACK_NAME}" =~ ^[a-z0-9][a-z0-9_-]{1,62}$ ]]; then
  fail "STACK_NAME must be a stable lowercase Compose project name"
fi
if [[ ! "${DEPLOY_SHA}" =~ ^[a-f0-9]{40}$ ]]; then
  fail "DEPLOY_SHA must be a full 40-character commit SHA"
fi
if [[ "${BACKEND_URL}" != http://* || "${FRONTEND_URL}" != http://* ]]; then
  fail "BACKEND_URL and FRONTEND_URL must preserve the controlled intranet HTTP boundary"
fi

validate_digest_reference HOMEFIN_BACKEND_IMAGE
validate_digest_reference HOMEFIN_FRONTEND_IMAGE
validate_absolute_directory HOMEFIN_BACKUP_DIR
validate_absolute_directory HOMEFIN_DEPLOY_STATE_DIR

command -v docker >/dev/null || fail "docker is required"
command -v curl >/dev/null || fail "curl is required"
docker compose version >/dev/null || fail "Docker Compose v2 is required"

mkdir -p "${HOMEFIN_BACKUP_DIR}" "${HOMEFIN_DEPLOY_STATE_DIR}"
readonly CURRENT_STATE="${HOMEFIN_DEPLOY_STATE_DIR}/current.tsv"
readonly PREVIOUS_STATE="${HOMEFIN_DEPLOY_STATE_DIR}/previous.tsv"
readonly DEPLOY_LOCK="${HOMEFIN_DEPLOY_STATE_DIR}/deploy.lock"

if ! mkdir "${DEPLOY_LOCK}" 2>/dev/null; then
  fail "Another deployment may be active: ${DEPLOY_LOCK}"
fi
cleanup_lock() {
  rmdir "${DEPLOY_LOCK}" 2>/dev/null || true
}
trap cleanup_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

previous_backend=""
previous_frontend=""
if [[ -f "${CURRENT_STATE}" ]]; then
  previous_backend="$(state_value HOMEFIN_BACKEND_IMAGE "${CURRENT_STATE}")"
  previous_frontend="$(state_value HOMEFIN_FRONTEND_IMAGE "${CURRENT_STATE}")"
  validate_digest_value "${previous_backend}" "current backend image"
  validate_digest_value "${previous_frontend}" "current frontend image"
fi

log "Pulling immutable release images"
compose pull --policy always backend frontend

log "Starting and checking PostgreSQL before backup"
compose up --detach --no-build --wait db
create_database_backup

log "Running the release migration and initialization job"
if ! compose --profile migration run --rm --no-deps --no-build prestart; then
  fail "Migration failed; the existing application remains selected and no database downgrade was attempted"
fi

log "Starting release ${DEPLOY_SHA}"
if ! compose up --detach --no-build --wait backend frontend db-backup; then
  log "Compose failed to start the new application"
  deployment_healthy=false
else
  deployment_healthy=true
fi

if [[ "${deployment_healthy}" == "true" ]]; then
  wait_for_url "Backend" "${BACKEND_URL}/api/v1/utils/health-check/" ||
    deployment_healthy=false
fi
if [[ "${deployment_healthy}" == "true" ]]; then
  wait_for_url "Frontend" "${FRONTEND_URL}/" ||
    deployment_healthy=false
fi
if [[ "${deployment_healthy}" == "true" ]]; then
  wait_for_url "Frontend API proxy" "${FRONTEND_URL}/api/v1/utils/health-check/" ||
    deployment_healthy=false
fi

if [[ "${deployment_healthy}" != "true" ]]; then
  if [[ -z "${previous_backend}" || -z "${previous_frontend}" ]]; then
    fail "Release health checks failed and no prior image state is available for rollback"
  fi
  if rollback_images "${previous_backend}" "${previous_frontend}"; then
    fail "Release health checks failed; the previous application images were restored without changing the database schema"
  fi
  fail "Release health checks failed and image-only rollback also failed; manual recovery is required"
fi

if [[ -f "${CURRENT_STATE}" ]]; then
  cp "${CURRENT_STATE}" "${PREVIOUS_STATE}"
fi
write_state
log "Release ${DEPLOY_SHA} is healthy and deployment state is recorded"
