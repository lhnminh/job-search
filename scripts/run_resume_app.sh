#!/usr/bin/env bash

set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
RESUME_APP_UV_CACHE_DIR="${RESUME_APP_UV_CACHE_DIR:-/tmp/resume-app-uv-cache}"
cd "$REPOSITORY_ROOT"
exec env UV_CACHE_DIR="$RESUME_APP_UV_CACHE_DIR" uv run python webapp/server.py "$@"
