#!/usr/bin/env sh
# Activate .venv before running this script; Node is needed only for JS syntax checking.
set -eu
cd "$(dirname "$0")/.."
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pytest
node --check app/static/app.js
