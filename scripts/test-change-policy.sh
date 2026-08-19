#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
POLICY_SCRIPT="${REPO_ROOT}/scripts/change-policy.sh"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homefin-change-policy.XXXXXX")"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fail() {
  printf 'Change policy test failed: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local output="$1"
  local expected="$2"
  [[ "${output}" == *"${expected}"* ]] ||
    fail "expected output to contain: ${expected}"
}

printf '%s\n' "docs/development-guide.md" >"${TMP_DIR}/s-files"
output="$(FILES_FROM="${TMP_DIR}/s-files" bash "${POLICY_SCRIPT}")"
assert_contains "${output}" "Minimum risk: S"

printf '%s\n' "frontend/src/routes/_layout/budgets.tsx" >"${TMP_DIR}/m-files"
output="$(FILES_FROM="${TMP_DIR}/m-files" bash "${POLICY_SCRIPT}")"
assert_contains "${output}" "Minimum risk: M"

printf '%s\n' "AGENTS.md" >"${TMP_DIR}/policy-files"
output="$(FILES_FROM="${TMP_DIR}/policy-files" bash "${POLICY_SCRIPT}")"
assert_contains "${output}" "Minimum risk: M"

printf '%s\n' "backend/app/alembic/versions/example.py" >"${TMP_DIR}/h-files"
output="$(FILES_FROM="${TMP_DIR}/h-files" bash "${POLICY_SCRIPT}")"
assert_contains "${output}" "Minimum risk: H"

for high_risk_path in \
  "backend/app/api/deps.py" \
  "backend/app/models.py" \
  "frontend/src/hooks/useAuth.ts" \
  "uv.lock" \
  "compose.intranet.yml" \
  ".github/workflows/deploy-staging.yml"; do
  printf '%s\n' "${high_risk_path}" >"${TMP_DIR}/h-category-file"
  output="$(FILES_FROM="${TMP_DIR}/h-category-file" bash "${POLICY_SCRIPT}")"
  assert_contains "${output}" "Minimum risk: H"
done

if FILES_FROM="${TMP_DIR}/m-files" \
  CHANGE_RISK=S \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture" \
  TEST_EVIDENCE="fixture" \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "M path accepted an S declaration"
fi

if FILES_FROM="${TMP_DIR}/h-files" \
  CHANGE_RISK=M \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture" \
  TEST_EVIDENCE="fixture" \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "H path accepted an M declaration"
fi

if FILES_FROM="${TMP_DIR}/m-files" \
  CHANGE_RISK=M \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture" \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "check accepted missing test evidence"
fi

FILES_FROM="${TMP_DIR}/m-files" \
  CHANGE_RISK=M \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture behavior is unchanged" \
  TEST_EVIDENCE="fixture test passed" \
  bash "${POLICY_SCRIPT}" --check >/dev/null

if FILES_FROM="${TMP_DIR}/m-files" \
  CHANGE_RISK=M \
  CONTEXT_IMPACT=updated \
  TEST_EVIDENCE="fixture" \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "updated context impact was accepted without a context file"
fi

if FILES_FROM="${TMP_DIR}/h-files" \
  CHANGE_RISK=H \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture" \
  TEST_EVIDENCE="fixture" \
  ROLLBACK_EVIDENCE="fixture" \
  MIGRATION_EVIDENCE="fixture" \
  STAGING_EVIDENCE="  " \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "H declaration accepted blank staging evidence"
fi

if FILES_FROM="${TMP_DIR}/h-files" \
  CHANGE_RISK=H \
  CONTEXT_IMPACT=none \
  CONTEXT_REASON="fixture" \
  TEST_EVIDENCE="fixture" \
  ROLLBACK_EVIDENCE="fixture" \
  MIGRATION_EVIDENCE="N/A: no migration" \
  STAGING_EVIDENCE="N/A: unavailable" \
  bash "${POLICY_SCRIPT}" --check >/dev/null 2>&1; then
  fail "H declaration accepted N/A staging evidence"
fi

printf '%s\n' \
  "backend/app/alembic/versions/example.py" \
  "context/data-schema.md" >"${TMP_DIR}/h-context-files"
FILES_FROM="${TMP_DIR}/h-context-files" \
  CHANGE_RISK=H \
  CONTEXT_IMPACT=updated \
  TEST_EVIDENCE="full fixture suite" \
  ROLLBACK_EVIDENCE="fixture rollback" \
  MIGRATION_EVIDENCE="fixture migration" \
  STAGING_EVIDENCE="fixture staging" \
  bash "${POLICY_SCRIPT}" --check >/dev/null

printf 'Change policy tests passed.\n'
