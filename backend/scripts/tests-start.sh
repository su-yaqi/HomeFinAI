#! /usr/bin/env bash
set -e
set -x

main_database="${POSTGRES_DB:-app}"
export POSTGRES_DB="${POSTGRES_TEST_DB:-${main_database}_test}"

cleanup_test_database() {
    python scripts/test_database.py drop
}
trap cleanup_test_database EXIT

python scripts/test_database.py create
python app/tests_pre_start.py
alembic upgrade head

bash scripts/test.sh "$@"
