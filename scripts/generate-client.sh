#!/usr/bin/env bash

set -Eeuo pipefail

# OpenAPI generation only imports the application; it must also work in clean CI
# checkouts that intentionally have no deployment .env file.
export PROJECT_NAME="${PROJECT_NAME:-HomeFin}"
export POSTGRES_SERVER="${POSTGRES_SERVER:-localhost}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_DB="${POSTGRES_DB:-app}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-schema-generation-db-password}"
export FIRST_SUPERUSER="${FIRST_SUPERUSER:-admin@example.com}"
export FIRST_SUPERUSER_PASSWORD="${FIRST_SUPERUSER_PASSWORD:-schema-generation-admin-password}"

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/
bun run --filter frontend generate-client
# The legacy SDK plugin emits indentation on blank lines under Linux. Normalize
# generated sources so the artifact check is deterministic across platforms.
find frontend/src/client -type f -name '*.ts' \
  -exec perl -pi -e 's/[ \t]+$//' {} +
bun run lint
