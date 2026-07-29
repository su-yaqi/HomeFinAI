#!/usr/bin/env bash

set -Eeuo pipefail

exec bash scripts/dev.sh test-backend "$@"
