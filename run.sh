#!/usr/bin/env bash
# Starts the LegalListen website on http://localhost:8000 (reads GEMINI_API_KEY etc. from .env if present)
set -a; [ -f .env ] && . ./.env; set +a
exec .venv/bin/python -m uvicorn legallisten.app:app --host 127.0.0.1 --port 8000
