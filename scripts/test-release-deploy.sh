#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
FIXTURE_DIR="${SCRIPT_DIR}/test-fixtures"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homefin-release-test.XXXXXX")"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "${TMP_DIR}/bin" "${TMP_DIR}/backups" "${TMP_DIR}/state"
ln -s "${FIXTURE_DIR}/release-docker" "${TMP_DIR}/bin/docker"
ln -s "${FIXTURE_DIR}/release-curl" "${TMP_DIR}/bin/curl"

export PATH="${TMP_DIR}/bin:${PATH}"
export MOCK_DOCKER_LOG="${TMP_DIR}/docker.log"
export MOCK_CURL_COUNT_FILE="${TMP_DIR}/curl-count"
export STACK_NAME="homefin-release-test"
export HOMEFIN_BACKUP_DIR="${TMP_DIR}/backups"
export HOMEFIN_DEPLOY_STATE_DIR="${TMP_DIR}/state"
export BACKEND_URL="http://127.0.0.1:23000"
export FRONTEND_URL="http://127.0.0.1:23080"
export SECRET_KEY="release-test-secret"
export FIRST_SUPERUSER="admin@example.com"
export FIRST_SUPERUSER_PASSWORD="release-test-admin-password"
export POSTGRES_PASSWORD="release-test-db-password"
export POSTGRES_USER="postgres"
export POSTGRES_DB="app"
export FRONTEND_HOST="${FRONTEND_URL}"
export BACKEND_CORS_ORIGINS="${FRONTEND_URL}"
export HEALTHCHECK_ATTEMPTS=1
export HEALTHCHECK_INTERVAL_SECONDS=0

readonly OLD_SHA="1111111111111111111111111111111111111111"
readonly NEW_SHA="2222222222222222222222222222222222222222"
readonly FAIL_SHA="3333333333333333333333333333333333333333"
readonly OLD_BACKEND="ghcr.io/example/homefin/backend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
readonly OLD_FRONTEND="ghcr.io/example/homefin/frontend@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
readonly NEW_BACKEND="ghcr.io/example/homefin/backend@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
readonly NEW_FRONTEND="ghcr.io/example/homefin/frontend@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"

run_deploy() {
  export MOCK_DEPLOY_MODE="$1"
  export DEPLOY_SHA="$2"
  export HOMEFIN_BACKEND_IMAGE="$3"
  export HOMEFIN_FRONTEND_IMAGE="$4"
  : >"${MOCK_CURL_COUNT_FILE}"
  bash "${REPO_ROOT}/scripts/deploy-release.sh"
}

run_deploy success "${OLD_SHA}" "${OLD_BACKEND}" "${OLD_FRONTEND}"
grep -F $'DEPLOY_SHA\t1111111111111111111111111111111111111111' \
  "${HOMEFIN_DEPLOY_STATE_DIR}/current.tsv" >/dev/null
grep -F $'HOMEFIN_BACKEND_IMAGE\t'"${OLD_BACKEND}" \
  "${HOMEFIN_DEPLOY_STATE_DIR}/current.tsv" >/dev/null
find "${HOMEFIN_BACKUP_DIR}" -type f -name '*.dump' -size +0c | grep -q .

: >"${MOCK_DOCKER_LOG}"
set +e
run_deploy rollback "${NEW_SHA}" "${NEW_BACKEND}" "${NEW_FRONTEND}"
rollback_status=$?
set -e
if [[ "${rollback_status}" -eq 0 ]]; then
  printf 'A failed release must report failure after restoring prior images.\n' >&2
  exit 1
fi
grep -F "backend=${OLD_BACKEND}" "${MOCK_DOCKER_LOG}" >/dev/null
grep -F "frontend=${OLD_FRONTEND}" "${MOCK_DOCKER_LOG}" >/dev/null
grep -F $'DEPLOY_SHA\t1111111111111111111111111111111111111111' \
  "${HOMEFIN_DEPLOY_STATE_DIR}/current.tsv" >/dev/null

: >"${MOCK_DOCKER_LOG}"
set +e
run_deploy migration-fail "${FAIL_SHA}" "${NEW_BACKEND}" "${NEW_FRONTEND}"
migration_status=$?
set -e
if [[ "${migration_status}" -eq 0 ]]; then
  printf 'A failed migration must stop deployment.\n' >&2
  exit 1
fi
grep -F " run " "${MOCK_DOCKER_LOG}" | grep -F " prestart" >/dev/null
if grep -F " up " "${MOCK_DOCKER_LOG}" | grep -F " backend frontend db-backup" >/dev/null; then
  printf 'Application services started after a failed migration.\n' >&2
  exit 1
fi

: >"${MOCK_DOCKER_LOG}"
set +e
run_deploy backup-fail "${FAIL_SHA}" "${NEW_BACKEND}" "${NEW_FRONTEND}"
backup_status=$?
set -e
if [[ "${backup_status}" -eq 0 ]]; then
  printf 'A failed backup must stop deployment.\n' >&2
  exit 1
fi
if grep -F " run " "${MOCK_DOCKER_LOG}" | grep -F " prestart" >/dev/null; then
  printf 'Migration started after a failed backup.\n' >&2
  exit 1
fi

set +e
HOMEFIN_BACKEND_IMAGE="ghcr.io/example/homefin/backend:mutable" \
  run_deploy success "${NEW_SHA}" \
  "ghcr.io/example/homefin/backend:mutable" \
  "${NEW_FRONTEND}" >/dev/null 2>&1
mutable_status=$?
set -e
if [[ "${mutable_status}" -eq 0 ]]; then
  printf 'Mutable release image references must be rejected.\n' >&2
  exit 1
fi

printf 'Release deployment safety tests passed.\n'
