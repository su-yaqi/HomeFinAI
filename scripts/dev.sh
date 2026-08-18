#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

DEV_PROJECT="${DEV_PROJECT:-homefin}"
DEV_SLOT="${DEV_SLOT:-0}"
DEV_PORT_BASE="${DEV_PORT_BASE:-21000}"
PORT_STRIDE=20
MAX_DEV_SLOT=999

fail() {
  printf 'HomeFin dev error: %s\n' "$*" >&2
  exit 1
}

if [[ ! "${DEV_PROJECT}" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  fail "DEV_PROJECT must use lowercase letters, digits, underscores, or hyphens"
fi
if [[ ! "${DEV_SLOT}" =~ ^[0-9]+$ ]] || ((DEV_SLOT > MAX_DEV_SLOT)); then
  fail "DEV_SLOT must be an integer from 0 to ${MAX_DEV_SLOT}"
fi
if [[ ! "${DEV_PORT_BASE}" =~ ^[0-9]+$ ]] || ((DEV_PORT_BASE < 1)); then
  fail "DEV_PORT_BASE must be a positive integer"
fi

PORT_BLOCK_START=$((DEV_PORT_BASE + DEV_SLOT * PORT_STRIDE))
HOMEFIN_FRONTEND_PORT="${PORT_BLOCK_START}"
HOMEFIN_BACKEND_PORT=$((PORT_BLOCK_START + 1))
HOMEFIN_DB_PORT=$((PORT_BLOCK_START + 2))
HOMEFIN_ADMINER_PORT=$((PORT_BLOCK_START + 3))
HOMEFIN_MAIL_UI_PORT=$((PORT_BLOCK_START + 4))
HOMEFIN_MAIL_SMTP_PORT=$((PORT_BLOCK_START + 5))
HOMEFIN_PLAYWRIGHT_UI_PORT=$((PORT_BLOCK_START + 6))

if ((HOMEFIN_PLAYWRIGHT_UI_PORT > 65535)); then
  fail "DEV_PORT_BASE and DEV_SLOT produce ports above 65535"
fi

MAIN_PROJECT="${DEV_PROJECT}-dev-${DEV_SLOT}"
ACTIVE_PROJECT="${MAIN_PROJECT}"
HOMEFIN_FRONTEND_URL="http://127.0.0.1:${HOMEFIN_FRONTEND_PORT}"
HOMEFIN_BACKEND_URL="http://127.0.0.1:${HOMEFIN_BACKEND_PORT}"

export DEV_PROJECT DEV_SLOT DEV_PORT_BASE
export HOMEFIN_FRONTEND_PORT HOMEFIN_BACKEND_PORT HOMEFIN_DB_PORT
export HOMEFIN_ADMINER_PORT HOMEFIN_MAIL_UI_PORT HOMEFIN_MAIL_SMTP_PORT
export HOMEFIN_PLAYWRIGHT_UI_PORT HOMEFIN_FRONTEND_URL HOMEFIN_BACKEND_URL
export HOMEFIN_WORKSPACE_ID="${REPO_ROOT}"
export FRONTEND_HOST="${HOMEFIN_FRONTEND_URL}"
export BACKEND_CORS_ORIGINS="${HOMEFIN_FRONTEND_URL}"
export INTRANET_API_URL="${HOMEFIN_BACKEND_URL}"

select_project() {
  ACTIVE_PROJECT="$1"
  export COMPOSE_PROJECT_NAME="${ACTIVE_PROJECT}"
  export DOCKER_IMAGE_BACKEND="${ACTIVE_PROJECT}-backend"
  export DOCKER_IMAGE_FRONTEND="${ACTIVE_PROJECT}-frontend"
}

select_project "${MAIN_PROJECT}"

compose_base() {
  docker compose \
    --project-name "${ACTIVE_PROJECT}" \
    --file compose.yml \
    --file compose.override.yml \
    "$@"
}

compose_mail_ui() {
  docker compose \
    --project-name "${ACTIVE_PROJECT}" \
    --file compose.yml \
    --file compose.override.yml \
    --file compose.dev-mail.yml \
    "$@"
}

compose_playwright_ui() {
  docker compose \
    --project-name "${ACTIVE_PROJECT}" \
    --file compose.yml \
    --file compose.override.yml \
    --file compose.dev-playwright.yml \
    "$@"
}

compose_test() {
  docker compose \
    --project-name "${ACTIVE_PROJECT}" \
    --file compose.yml \
    --file compose.override.yml \
    --file compose.test.yml \
    "$@"
}

require_docker() {
  command -v docker >/dev/null 2>&1 || fail "Docker CLI is not installed"
  docker info >/dev/null 2>&1 || fail "Docker daemon is not available"
}

check_project_ownership() {
  local rows name working_dir volume workspace_id
  rows="$(
    docker ps -a \
      --filter "label=com.docker.compose.project=${ACTIVE_PROJECT}" \
      --format '{{.Names}}|{{.Label "com.docker.compose.project.working_dir"}}'
  )"
  if [[ -n "${rows}" ]]; then
    while IFS='|' read -r name working_dir; do
      if [[ -z "${working_dir}" || "${working_dir}" != "${REPO_ROOT}" ]]; then
        printf 'Compose project %s is already associated with another workspace:\n' \
          "${ACTIVE_PROJECT}" >&2
        printf '  container: %s\n  workspace: %s\n' \
          "${name}" "${working_dir:-unknown}" >&2
        fail "choose another DEV_SLOT; existing containers were not changed"
      fi
    done <<<"${rows}"
  fi

  rows="$(
    docker volume ls \
      --filter "label=com.docker.compose.project=${ACTIVE_PROJECT}" \
      --format '{{.Name}}|{{.Label "com.homefin.dev.workspace"}}'
  )"
  if [[ -n "${rows}" ]]; then
    while IFS='|' read -r volume workspace_id; do
      if [[ -z "${workspace_id}" || "${workspace_id}" != "${REPO_ROOT}" ]]; then
        printf 'Compose project %s has a volume owned by another workspace:\n' \
          "${ACTIVE_PROJECT}" >&2
        printf '  volume: %s\n  workspace: %s\n' \
          "${volume}" "${workspace_id:-unknown}" >&2
        fail "choose another DEV_SLOT; the existing volume was not changed"
      fi
    done <<<"${rows}"
  fi
}

check_port() {
  local port label rows container project service working_dir listeners
  port="$1"
  label="$2"
  rows="$(
    docker ps \
      --filter "publish=${port}" \
      --format '{{.Names}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}|{{.Label "com.docker.compose.project.working_dir"}}'
  )"

  if [[ -n "${rows}" ]]; then
    while IFS='|' read -r container project service working_dir; do
      if [[ "${project}" == "${ACTIVE_PROJECT}" && "${working_dir}" == "${REPO_ROOT}" ]]; then
        continue
      fi
      printf 'Port %s (%s) is occupied by Docker container %s' \
        "${port}" "${label}" "${container}" >&2
      if [[ -n "${project}" ]]; then
        printf ' [project=%s service=%s]' "${project}" "${service:-unknown}" >&2
      fi
      printf '.\n' >&2
      fail "the existing container was not stopped or removed"
    done <<<"${rows}"
    return
  fi

  if command -v lsof >/dev/null 2>&1; then
    listeners="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${listeners}" ]]; then
      printf 'Port %s (%s) is occupied by a host process:\n%s\n' \
        "${port}" "${label}" "${listeners}" >&2
      fail "the existing process was not stopped"
    fi
  elif (echo >/dev/tcp/127.0.0.1/"${port}") >/dev/null 2>&1; then
    fail "port ${port} (${label}) has a non-Docker listener; process details are unavailable"
  fi
}

check_ports() {
  local item port label
  for item in "$@"; do
    port="${item%%:*}"
    label="${item#*:}"
    check_port "${port}" "${label}"
  done
}

check_core() {
  require_docker
  check_project_ownership
  check_ports \
    "${HOMEFIN_FRONTEND_PORT}:frontend" \
    "${HOMEFIN_BACKEND_PORT}:backend"
}

ensure_test_project_idle() {
  local running
  running="$(
    docker ps \
      --filter "label=com.docker.compose.project=${ACTIVE_PROJECT}" \
      --format '{{.Names}}'
  )"
  if [[ -n "${running}" ]]; then
    printf 'Test project %s is already running:\n%s\n' \
      "${ACTIVE_PROJECT}" "${running}" >&2
    fail "wait for the existing test run or choose another DEV_SLOT"
  fi
}

print_environment() {
  printf 'Project:        %s\n' "${MAIN_PROJECT}"
  printf 'Workspace:      %s\n' "${REPO_ROOT}"
  printf 'DEV_SLOT:       %s\n' "${DEV_SLOT}"
  printf 'Port block:     %s-%s\n' "${PORT_BLOCK_START}" "$((PORT_BLOCK_START + PORT_STRIDE - 1))"
  printf 'Frontend:       %s\n' "${HOMEFIN_FRONTEND_URL}"
  printf 'Backend:        %s\n' "${HOMEFIN_BACKEND_URL}"
  printf 'API docs:       %s/docs\n' "${HOMEFIN_BACKEND_URL}"
  printf 'Database:       127.0.0.1:%s (not exposed by default)\n' "${HOMEFIN_DB_PORT}"
  printf 'Adminer:        http://127.0.0.1:%s (on demand)\n' "${HOMEFIN_ADMINER_PORT}"
  printf 'Mailcatcher UI: http://127.0.0.1:%s (on demand)\n' "${HOMEFIN_MAIL_UI_PORT}"
  printf 'Mail SMTP:      127.0.0.1:%s (on demand)\n' "${HOMEFIN_MAIL_SMTP_PORT}"
  printf 'Playwright UI:  http://127.0.0.1:%s (on demand)\n' "${HOMEFIN_PLAYWRIGHT_UI_PORT}"
}

cleanup_test_project() {
  compose_test \
    --profile adminer \
    --profile mail \
    --profile playwright \
    down --volumes --remove-orphans
}

finish_test_project() {
  local status="$1"
  trap - EXIT INT TERM
  if ! cleanup_test_project; then
    printf 'HomeFin dev error: failed to clean test project %s.\n' \
      "${ACTIVE_PROJECT}" >&2
    if ((status == 0)); then
      status=1
    fi
  fi
  exit "${status}"
}

command_name="${1:-help}"
shift || true

case "${command_name}" in
  env)
    print_environment
    ;;
  check)
    check_core
    printf 'Project ownership and core ports are available for %s.\n' "${MAIN_PROJECT}"
    ;;
  config)
    compose_base config --quiet
    print_environment
    ;;
  up)
    check_core
    compose_base up --detach --build backend frontend
    print_environment
    ;;
  restart)
    check_core
    compose_base up --detach --force-recreate backend frontend
    print_environment
    ;;
  down)
    require_docker
    check_project_ownership
    compose_base \
      --profile adminer \
      --profile mail \
      --profile playwright \
      down --remove-orphans
    ;;
  status)
    require_docker
    check_project_ownership
    compose_base ps
    ;;
  logs)
    require_docker
    check_project_ownership
    compose_base logs --tail=200 "$@"
    ;;
  adminer-up)
    require_docker
    check_project_ownership
    check_ports "${HOMEFIN_ADMINER_PORT}:adminer"
    compose_base --profile adminer up --detach adminer
    printf 'Adminer: http://127.0.0.1:%s\n' "${HOMEFIN_ADMINER_PORT}"
    ;;
  adminer-down)
    require_docker
    check_project_ownership
    compose_base --profile adminer stop adminer
    ;;
  mail-up)
    require_docker
    check_project_ownership
    check_ports \
      "${HOMEFIN_MAIL_UI_PORT}:mailcatcher-ui" \
      "${HOMEFIN_MAIL_SMTP_PORT}:mailcatcher-smtp"
    compose_mail_ui --profile mail up --detach mailcatcher
    printf 'Mailcatcher UI: http://127.0.0.1:%s\n' "${HOMEFIN_MAIL_UI_PORT}"
    printf 'Mailcatcher SMTP: 127.0.0.1:%s\n' "${HOMEFIN_MAIL_SMTP_PORT}"
    ;;
  mail-down)
    require_docker
    check_project_ownership
    compose_mail_ui --profile mail stop mailcatcher
    ;;
  playwright-ui)
    require_docker
    local_backend="$(
      docker ps \
        --filter "label=com.docker.compose.project=${ACTIVE_PROJECT}" \
        --filter "label=com.docker.compose.service=backend" \
        --format '{{.Names}}'
    )"
    check_project_ownership
    check_ports \
      "${HOMEFIN_BACKEND_PORT}:backend" \
      "${HOMEFIN_PLAYWRIGHT_UI_PORT}:playwright-ui"
    printf 'Playwright UI: http://127.0.0.1:%s\n' "${HOMEFIN_PLAYWRIGHT_UI_PORT}"
    if [[ -z "${local_backend}" ]]; then
      compose_base --profile playwright up --detach --build backend
    fi
    compose_base --profile playwright up --detach --no-deps mailcatcher
    compose_playwright_ui \
      --profile playwright \
      run --rm --service-ports --no-deps playwright \
      bunx playwright test --ui --ui-host=0.0.0.0 --ui-port=9323 "$@"
    ;;
  test-backend)
    require_docker
    select_project "${MAIN_PROJECT}-test-backend"
    check_project_ownership
    ensure_test_project_idle
    cleanup_test_project >/dev/null
    trap 'finish_test_project $?' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    compose_test build backend
    compose_test up --detach db
    compose_test run --rm prestart
    compose_test run --rm --no-deps backend \
      bash -lc 'cd /app/backend && exec uv run bash scripts/tests-start.sh "$@"' \
      bash "$@"
    trap - EXIT INT TERM
    cleanup_test_project
    ;;
  test-e2e)
    require_docker
    select_project "${MAIN_PROJECT}-test-e2e"
    check_project_ownership
    ensure_test_project_idle
    cleanup_test_project >/dev/null
    trap 'finish_test_project $?' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    compose_test --profile playwright build backend playwright
    compose_test --profile playwright run --rm playwright \
      bunx playwright test "$@"
    trap - EXIT INT TERM
    cleanup_test_project
    ;;
  help|-h|--help)
    make help
    ;;
  *)
    fail "unknown command: ${command_name}"
    ;;
esac
