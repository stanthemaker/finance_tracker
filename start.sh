#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Finance Tracker..."

# backend
(
  cd "$ROOT/backend"
  conda run -n finance_tracker uvicorn main:app --reload --port 8000
) &
BACKEND_PID=$!

# frontend
(
  cd "$ROOT/frontend"
  npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
