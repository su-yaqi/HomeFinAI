#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "${REPO_ROOT}"

MODE="plan"
BASE_REF="${BASE_REF:-}"
FILES_FROM="${FILES_FROM:-}"
CHANGE_RISK="${CHANGE_RISK:-}"
CONTEXT_IMPACT="${CONTEXT_IMPACT:-}"
CONTEXT_REASON="${CONTEXT_REASON:-}"
TEST_EVIDENCE="${TEST_EVIDENCE:-}"
ROLLBACK_EVIDENCE="${ROLLBACK_EVIDENCE:-}"
MIGRATION_EVIDENCE="${MIGRATION_EVIDENCE:-}"
STAGING_EVIDENCE="${STAGING_EVIDENCE:-}"

usage() {
  cat <<'EOF'
Usage:
  scripts/change-policy.sh [--check] [--base REF] [--files-from FILE]

Plan mode reports the inferred minimum risk for changed files.
Check mode also validates CHANGE_RISK, CONTEXT_IMPACT, and evidence variables.

Environment:
  CHANGE_RISK=S|M|H
  CONTEXT_IMPACT=updated|none
  CONTEXT_REASON=...              required when impact is none
  TEST_EVIDENCE=...               required in check mode
  ROLLBACK_EVIDENCE=...           required for H
  MIGRATION_EVIDENCE=...          required for H
  STAGING_EVIDENCE=...            required for H
  BASE_REF=...                    inspect BASE_REF...HEAD
  FILES_FROM=...                  read one changed path per line
EOF
}

fail() {
  printf 'Change policy error: %s\n' "$*" >&2
  exit 1
}

reject_not_applicable() {
  local name="$1"
  local value="$2"
  local normalized
  normalized="$(
    printf '%s' "${value}" |
      tr '[:upper:]' '[:lower:]' |
      tr -d '[:space:]'
  )"
  case "${normalized}" in
    n/a*|na|na:*|notapplicable*)
      fail "${name} cannot be N/A for H"
      ;;
  esac
}

while (($# > 0)); do
  case "$1" in
    --check)
      MODE="check"
      shift
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

  if [[ -n "${BASE_REF}" ]]; then
    git rev-parse --verify "${BASE_REF}^{commit}" >/dev/null 2>&1 ||
      fail "base ref is not a commit: ${BASE_REF}"
    while IFS= read -r file; do
      changed_files+=("${file}")
    done < <(
      git diff --name-only --diff-filter=ACMRD "${BASE_REF}...HEAD" | sort -u
    )
    return
  fi

  while IFS= read -r file; do
    changed_files+=("${file}")
  done < <(
    {
      git diff --cached --name-only --diff-filter=ACMRD
      git diff --name-only --diff-filter=ACMRD
      git ls-files --others --exclude-standard
    } | sed '/^[[:space:]]*$/d' | sort -u
  )
}

risk_rank() {
  case "$1" in
    S) printf '1\n' ;;
    M) printf '2\n' ;;
    H) printf '3\n' ;;
    *) return 1 ;;
  esac
}

minimum_risk="S"
declare -a reasons=()

raise_risk() {
  local requested="$1"
  local reason="$2"
  if (( $(risk_rank "${requested}") > $(risk_rank "${minimum_risk}") )); then
    minimum_risk="${requested}"
  fi
  reasons+=("${reason}")
}

classify_file() {
  local file="$1"

  case "${file}" in
    backend/app/alembic/*|backend/app/models.py|\
    backend/app/api/deps.py|backend/app/api/agent_auth.py|backend/app/crud.py|\
    backend/app/core/config.py|backend/app/core/db.py|backend/app/core/security.py|\
    backend/app/api/routes/login.py|backend/app/api/routes/users.py|\
    backend/app/api/routes/private.py|backend/app/api/routes/api_tokens.py|\
    backend/app/*auth*|\
    frontend/src/hooks/useAuth.ts|frontend/src/routes/login.tsx|\
    frontend/src/routes/recover-password.tsx|frontend/src/routes/reset-password.tsx|\
    frontend/src/routes/signup.tsx|\
    frontend/src/routes/_layout/system.accounts.tsx|\
    frontend/src/routes/_layout/system.api-tokens.tsx)
      raise_risk "H" "${file}: authentication, permissions, security, model, or migration boundary"
      return
      ;;
    pyproject.toml|backend/pyproject.toml|package.json|frontend/package.json|\
    uv.lock|bun.lock|Dockerfile|*/Dockerfile|*/Dockerfile.*|\
    .pre-commit-config.yaml|.github/dependabot.yml)
      raise_risk "H" "${file}: dependency or build-tool boundary"
      return
      ;;
    compose.yml|compose.intranet.yml|.env*.example|\
    .github/workflows/deploy-*.yml|.github/workflows/deploy-*.yaml)
      raise_risk "H" "${file}: deployment or formal runtime boundary"
      return
      ;;
    AGENTS.md)
      raise_risk "M" "${file}: repository-wide engineering policy"
      return
      ;;
    backend/tests/*|frontend/tests/*|*.md|context/*|frontend/src/*.css|\
    frontend/src/*/*.css)
      return
      ;;
    backend/*|frontend/*|scripts/*|Makefile|compose*.yml|.github/*)
      raise_risk "M" "${file}: production code or engineering workflow"
      return
      ;;
  esac
}

collect_files

if ((${#changed_files[@]} == 0)); then
  if [[ "${MODE}" == "check" ]]; then
    fail "no changed files found"
  fi
  printf 'No changed files found.\n'
  exit 0
fi

for file in "${changed_files[@]}"; do
  classify_file "${file}"
done

printf 'Changed files: %s\n' "${#changed_files[@]}"
printf 'Minimum risk: %s\n' "${minimum_risk}"
if ((${#reasons[@]} > 0)); then
  printf 'Reasons:\n'
  printf '  - %s\n' "${reasons[@]}"
fi
printf 'Reminder: semantic risk can only raise this level.\n'

if [[ "${MODE}" != "check" ]]; then
  exit 0
fi

risk_rank "${CHANGE_RISK}" >/dev/null 2>&1 ||
  fail "CHANGE_RISK must be S, M, or H"
if (( $(risk_rank "${CHANGE_RISK}") < $(risk_rank "${minimum_risk}") )); then
  fail "declared risk ${CHANGE_RISK} is below inferred minimum ${minimum_risk}"
fi

case "${CONTEXT_IMPACT}" in
  updated)
    context_changed="false"
    for file in "${changed_files[@]}"; do
      if [[ "${file}" == context/* ]]; then
        context_changed="true"
        break
      fi
    done
    [[ "${context_changed}" == "true" ]] ||
      fail "CONTEXT_IMPACT=updated but no context/ file is changed"
    ;;
  none)
    [[ "${CONTEXT_REASON}" =~ [^[:space:]] ]] ||
      fail "CONTEXT_REASON is required when CONTEXT_IMPACT=none"
    ;;
  *)
    fail "CONTEXT_IMPACT must be updated or none"
    ;;
esac

[[ "${TEST_EVIDENCE}" =~ [^[:space:]] ]] || fail "TEST_EVIDENCE is required"

if [[ "${CHANGE_RISK}" == "H" ]]; then
  [[ "${ROLLBACK_EVIDENCE}" =~ [^[:space:]] ]] ||
    fail "ROLLBACK_EVIDENCE is required for H"
  [[ "${MIGRATION_EVIDENCE}" =~ [^[:space:]] ]] ||
    fail "MIGRATION_EVIDENCE is required for H"
  [[ "${STAGING_EVIDENCE}" =~ [^[:space:]] ]] ||
    fail "STAGING_EVIDENCE is required for H"
  reject_not_applicable "ROLLBACK_EVIDENCE" "${ROLLBACK_EVIDENCE}"
  reject_not_applicable "STAGING_EVIDENCE" "${STAGING_EVIDENCE}"
fi

printf 'Declared risk: %s\n' "${CHANGE_RISK}"
printf 'Context impact: %s\n' "${CONTEXT_IMPACT}"
printf 'Change policy declarations are complete.\n'
