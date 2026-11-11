#!/usr/bin/env bash
# One-time setup on macOS / Linux: creates .venv with Python 3.11 and installs everything.
set -e
PY=$(command -v python3.11 || command -v python3)
"$PY" -c 'import sys; assert sys.version_info[:2] >= (3, 11), "Python 3.11+ required"'
"$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
[ -f .env ] || cp .env.example .env
echo "Setup done. Start the website with:  bash run.sh   (then open http://localhost:8000)"
