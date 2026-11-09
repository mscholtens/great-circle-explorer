#!/usr/bin/env bash
# Starts backend (FastAPI, :8000) and frontend (Vite, :5173) with one command. Ctrl+C stops both.
# First run: creates backend/.venv and runs `npm install` (needs internet once, for the packages).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x backend/.venv/bin/uvicorn ]; then
  echo "▸ Setting up the Python environment (first run only)…"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --quiet -e 'backend[dev]'
fi
if [ ! -d frontend/node_modules ]; then
  echo "▸ Installing frontend packages (first run only)…"
  (cd frontend && npm install --no-audit --no-fund)
fi

pids=()
cleanup() { trap - INT TERM EXIT; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup INT TERM EXIT

(cd backend && exec .venv/bin/uvicorn app.main:app --reload --port 8000) &
pids+=($!)
(cd frontend && exec npm run dev) &
pids+=($!)

echo "▸ Open http://localhost:5173   (Ctrl+C stops both)"
wait -n   # if either process dies, stop the other too
