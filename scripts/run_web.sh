#!/usr/bin/env bash
# Start the ParkGuide web app at http://127.0.0.1:8513 (loopback only).
# Builds the frontend first when web/dist is missing or --build is given.
# Startup reads the existing SQLite database; it never ingests, indexes or
# embeds. Paid Azure calls happen only when a question is asked.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == "--build" || ! -f web/dist/index.html ]]; then
  npm --prefix web ci --ignore-scripts
  npm --prefix web run build
fi
exec .venv/bin/python -m parkguide.web
