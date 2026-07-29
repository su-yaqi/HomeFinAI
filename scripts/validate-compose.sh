#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homefin-compose-validation.XXXXXX")"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export STACK_NAME="${STACK_NAME:-homefin-compose-validation}"
export SECRET_KEY="${SECRET_KEY:-validation-secret-key-not-for-deployment}"
export FIRST_SUPERUSER="${FIRST_SUPERUSER:-admin@example.com}"
export FIRST_SUPERUSER_PASSWORD="${FIRST_SUPERUSER_PASSWORD:-validation-password}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-validation-password}"
export POSTGRES_DB="${POSTGRES_DB:-app}"
export FRONTEND_HOST="${FRONTEND_HOST:-http://127.0.0.1:8080}"
export BACKEND_CORS_ORIGINS="${BACKEND_CORS_ORIGINS:-http://127.0.0.1:8080}"
export INTRANET_API_URL="${INTRANET_API_URL:-http://127.0.0.1:8000}"

docker compose \
  --file compose.yml \
  --file compose.override.yml \
  --profile adminer \
  --profile mail \
  --profile playwright \
  config --quiet

intranet_config="${TMP_DIR}/intranet.yml"
docker compose \
  --file compose.yml \
  --file compose.intranet.yml \
  --profile ops \
  config >"${intranet_config}"

grep -F "db-backup:" "${intranet_config}" >/dev/null
grep -F "app-db-backups:" "${intranet_config}" >/dev/null
grep -F "SCHEDULE: '@daily'" "${intranet_config}" >/dev/null
grep -F "published: \"8000\"" "${intranet_config}" >/dev/null
grep -F "published: \"8080\"" "${intranet_config}" >/dev/null
grep -F "published: \"8081\"" "${intranet_config}" >/dev/null

printf 'Development and intranet Compose configurations are valid.\n'
