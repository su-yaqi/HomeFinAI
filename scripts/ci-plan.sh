#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

EVENT_NAME="${EVENT_NAME:-pull_request}"
BASE_REF="${BASE_REF:-}"
FILES_FROM="${FILES_FROM:-}"
GITHUB_OUTPUT_FILE="${GITHUB_OUTPUT_FILE:-}"

fail() {
  printf 'CI plan error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  scripts/ci-plan.sh [--event NAME] [--base REF] [--files-from FILE]
                     [--github-output FILE]

Pull requests are classified from their changed paths. Pushes to the default
branch, schedules, and manual runs always select the full suite.
EOF
}

while (($# > 0)); do
  case "$1" in
    --event)
      (($# >= 2)) || fail "--event requires a value"
      EVENT_NAME="$2"
      shift 2
      ;;
    --base)
      (($# >= 2)) || fail "--base requires a Git ref"
      BASE_REF="$2"
      shift 2
      ;;
    --files-from)
      (($# >= 2)) || fail "--files-from requires a file"
      FILES_FROM="$2"
      shift 2
      ;;
    --github-output)
      (($# >= 2)) || fail "--github-output requires a file"
      GITHUB_OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

declare -a changed_files=()

collect_files() {
  if [[ -n "${FILES_FROM}" ]]; then
    [[ -f "${FILES_FROM}" ]] || fail "file list does not exist: ${FILES_FROM}"
    while IFS= read -r file; do
      changed_files+=("${file}")
    done < <(sed '/^[[:space:]]*$/d' "${FILES_FROM}" | sort -u)
    return
  fi

  [[ -n "${BASE_REF}" ]] || fail "--base or --files-from is required for pull requests"
  git rev-parse --verify "${BASE_REF}^{commit}" >/dev/null 2>&1 ||
    fail "base ref is not a commit: ${BASE_REF}"
  while IFS= read -r file; do
    changed_files+=("${file}")
  done < <(
    git diff --name-only --diff-filter=ACMRD "${BASE_REF}...HEAD" | sort -u
  )
}

bool_or() {
  if [[ "$1" == "true" || "$2" == "true" ]]; then
    printf 'true\n'
  else
    printf 'false\n'
  fi
}

full="false"
backend="false"
frontend="false"
e2e="false"
compose="false"
artifacts="false"
risk="S"

case "${EVENT_NAME}" in
  pull_request)
    collect_files
    ;;
  push|schedule|workflow_dispatch)
    full="true"
    ;;
  *)
    fail "unsupported event: ${EVENT_NAME}"
    ;;
esac

if [[ "${full}" == "false" ]]; then
  policy_output="$(
    FILES_FROM="${FILES_FROM}" BASE_REF="${BASE_REF}" \
      bash "${SCRIPT_DIR}/change-policy.sh"
  )"
  risk="$(printf '%s\n' "${policy_output}" | sed -n 's/^Minimum risk: //p')"
  [[ "${risk}" =~ ^[SMH]$ ]] || fail "could not infer risk"

  for file in "${changed_files[@]}"; do
    case "${file}" in
      backend/*|pyproject.toml|uv.lock)
        backend="true"
        ;;
    esac
    case "${file}" in
      frontend/*|package.json|bun.lock)
        frontend="true"
        ;;
    esac
    case "${file}" in
      frontend/tests/*|frontend/src/*|backend/app/*|compose*.yml|\
      package.json|bun.lock|pyproject.toml|uv.lock)
        e2e="true"
        ;;
    esac
    case "${file}" in
      compose*.yml|Dockerfile|*/Dockerfile|*/Dockerfile.*|\
      scripts/dev.sh|scripts/validate-compose.sh|.github/workflows/*)
        compose="true"
        ;;
    esac
    case "${file}" in
      backend/app/*|backend/pyproject.toml|frontend/src/client/*|\
      frontend/package.json|scripts/generate-client.sh|compose*.yml|\
      Dockerfile|*/Dockerfile|*/Dockerfile.*|pyproject.toml|uv.lock|\
      package.json|bun.lock)
        artifacts="true"
        ;;
    esac
  done

  if [[ "${risk}" == "H" ]]; then
    backend="true"
    frontend="true"
    e2e="true"
    compose="true"
    artifacts="true"
  fi
else
  risk="H"
  backend="true"
  frontend="true"
  e2e="true"
  compose="true"
  artifacts="true"
fi

affected="$(bool_or "${backend}" "${frontend}")"

printf 'CI plan: event=%s risk=%s full=%s\n' "${EVENT_NAME}" "${risk}" "${full}"
printf '  backend=%s frontend=%s affected=%s e2e=%s compose=%s artifacts=%s\n' \
  "${backend}" "${frontend}" "${affected}" "${e2e}" "${compose}" "${artifacts}"

if [[ -n "${GITHUB_OUTPUT_FILE}" ]]; then
  {
    printf 'risk=%s\n' "${risk}"
    printf 'full=%s\n' "${full}"
    printf 'backend=%s\n' "${backend}"
    printf 'frontend=%s\n' "${frontend}"
    printf 'affected=%s\n' "${affected}"
    printf 'e2e=%s\n' "${e2e}"
    printf 'compose=%s\n' "${compose}"
    printf 'artifacts=%s\n' "${artifacts}"
  } >>"${GITHUB_OUTPUT_FILE}"
fi
