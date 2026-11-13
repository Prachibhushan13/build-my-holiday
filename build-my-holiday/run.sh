#!/usr/bin/env bash
# Build My Holiday — one command to run everything.
#   ./run.sh          install (first time), then serve API + UI on http://localhost:8000
#   ./run.sh dev      API on :8000 with auto-reload + Vite dev server on :5173
#   ./run.sh test     run the backend test-suite
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"

if [ ! -x .venv/bin/python ]; then
  echo "▶ Creating virtual environment…"
  "$PY" -m venv .venv
fi
if ! .venv/bin/python -c "import fastapi, uvicorn, pydantic" 2>/dev/null; then
  echo "▶ Installing backend dependencies…"
  .venv/bin/python -m pip install -q -r backend/requirements.txt
fi

if [ "${1:-}" = "test" ]; then
  cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest -q tests
  exit $?
fi

if [ "${1:-}" = "dev" ]; then
  [ -d frontend/node_modules ] || (cd frontend && npm install --no-audit --no-fund)
  (cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
  API=$!
  trap 'kill $API 2>/dev/null' EXIT
  cd frontend && npm run dev
  exit 0
fi

# Production-style: serve the prebuilt UI in frontend/dist (rebuilt only if it is missing and npm exists).
if [ ! -f frontend/dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "▶ Building the frontend…"
    (cd frontend && npm install --no-audit --no-fund && npm run build)
  else
    echo "⚠ frontend/dist is missing and npm is not installed — only the API will be served."
  fi
fi
echo "▶ Build My Holiday running at http://localhost:8000   (Ctrl+C to stop)"
cd backend && exec ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
