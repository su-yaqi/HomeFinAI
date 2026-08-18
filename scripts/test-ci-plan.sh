#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CI_PLAN="${SCRIPT_DIR}/ci-plan.sh"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homefin-ci-plan.XXXXXX")"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fail() {
  printf 'CI plan test failed: %s\n' "$*" >&2
  exit 1
}

assert_output() {
  local files="$1"
  local expected="$2"
  local output_file="${TMP_DIR}/outputs"
  : >"${output_file}"
  bash "${CI_PLAN}" \
    --event pull_request \
    --files-from "${files}" \
    --github-output "${output_file}" >/dev/null
  grep -Fx "${expected}" "${output_file}" >/dev/null ||
    fail "expected output: ${expected}"
}

printf '%s\n' "docs/development-guide.md" >"${TMP_DIR}/docs"
assert_output "${TMP_DIR}/docs" "risk=S"
assert_output "${TMP_DIR}/docs" "backend=false"
assert_output "${TMP_DIR}/docs" "e2e=false"

printf '%s\n' "backend/app/api/routes/budgets.py" >"${TMP_DIR}/backend"
assert_output "${TMP_DIR}/backend" "risk=M"
assert_output "${TMP_DIR}/backend" "backend=true"
assert_output "${TMP_DIR}/backend" "frontend=false"
assert_output "${TMP_DIR}/backend" "e2e=true"

printf '%s\n' "frontend/src/routes/_layout/budgets.tsx" >"${TMP_DIR}/frontend"
assert_output "${TMP_DIR}/frontend" "risk=M"
assert_output "${TMP_DIR}/frontend" "frontend=true"
assert_output "${TMP_DIR}/frontend" "backend=false"

printf '%s\n' "backend/app/api/routes/login.py" >"${TMP_DIR}/high"
assert_output "${TMP_DIR}/high" "risk=H"
assert_output "${TMP_DIR}/high" "backend=true"
assert_output "${TMP_DIR}/high" "frontend=true"
assert_output "${TMP_DIR}/high" "compose=true"
assert_output "${TMP_DIR}/high" "artifacts=true"

output_file="${TMP_DIR}/full-outputs"
: >"${output_file}"
bash "${CI_PLAN}" \
  --event schedule \
  --github-output "${output_file}" >/dev/null
for expected in risk=H full=true backend=true frontend=true e2e=true compose=true artifacts=true; do
  grep -Fx "${expected}" "${output_file}" >/dev/null ||
    fail "full run missing output: ${expected}"
done

printf 'CI plan tests passed.\n'
