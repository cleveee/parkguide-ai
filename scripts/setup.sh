#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PARKGUIDE_PYTHON="${PARKGUIDE_PYTHON:-python3}"
"$PARKGUIDE_PYTHON" -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 14), "Use Python 3.12 (supported: 3.11–3.13)"'
"$PARKGUIDE_PYTHON" -m venv .venv
PARKGUIDE_LOCK=requirements-full.lock
if [[ "${PARKGUIDE_CORE_ONLY:-0}" == "1" ]]; then
  PARKGUIDE_LOCK=requirements-core.lock
fi
if [[ -f "$PARKGUIDE_LOCK" ]]; then
  .venv/bin/python -m pip install -r "$PARKGUIDE_LOCK"
  .venv/bin/python -m pip install --no-deps -e .
else
  .venv/bin/python -m pip install -e '.[dev]'
fi
.venv/bin/parkguide init-db
.venv/bin/parkguide doctor
