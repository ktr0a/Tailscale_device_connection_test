#!/bin/bash
cd "$(dirname "$0")"
set -a && source .env && set +a
python3 -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
