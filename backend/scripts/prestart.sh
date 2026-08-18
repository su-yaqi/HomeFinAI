#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Stop before migration when legacy AI integrations require explicit cutover approval.
python app/legacy_ai_retirement_audit.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python app/initial_data.py
