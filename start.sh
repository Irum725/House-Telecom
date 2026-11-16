#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[House-Telecom] Starting setup and launch..."

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/5] Creating Python virtual environment .venv..."
  python3 -m venv .venv
fi

VENV_PY=".venv/bin/python"

if ! "$VENV_PY" -c "import fastapi, uvicorn, sqlalchemy" >/dev/null 2>&1; then
  echo "[2/5] Installing Python dependencies..."
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install -e .
else
  echo "[2/5] Python dependencies already installed."
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo "[3/5] Copying .env.example to .env..."
  cp .env.example .env
else
  echo "[3/5] .env already exists."
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "[4/5] Installing frontend dependencies..."
  (cd frontend && npm install)
else
  echo "[4/5] Frontend node_modules already installed."
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "[House-Telecom] Stopping servers..."
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "[5/5] Starting Backend (127.0.0.1:8001) and Frontend (localhost:4002)..."
"$VENV_PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!

(cd frontend && npm run dev -- --port 4002) &
FRONTEND_PID=$!

sleep 3
if command -v open >/dev/null 2>&1; then
  open "http://localhost:4002"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:4002"
fi

echo "[House-Telecom] Running at http://localhost:4002 (Press Ctrl+C to stop)"
wait
