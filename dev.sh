#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# dev.sh  —  Start OmniFlow in development mode (hot-reload)
#
# Usage: ./dev.sh
#
# Starts:
#   • Flask backend  → http://127.0.0.1:5001  (full API: check, download, …)
#   • Vite frontend  → http://localhost:5173   (hot-reload, proxies /api → :5001)
#
# Ctrl+C kills both processes cleanly.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Check .venv ─────────────────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/.venv/bin/python" ]]; then
  echo "❌  .venv not found. Run the one-time setup first:"
  echo "    python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ── Check node_modules ────────────────────────────────────────────────────
if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
  echo "📦  node_modules missing — installing…"
  (cd "$REPO_ROOT/frontend" && npm install)
fi

# ── Cleanup handler: kill both children on exit ───────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "🛑  Stopping servers…"
  [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait
  echo "✅  Done."
}
trap cleanup EXIT INT TERM

# ── Start backend ─────────────────────────────────────────────────────────
echo "🐍  Starting Flask backend on http://127.0.0.1:5001 …"
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/server.py" &
BACKEND_PID=$!

# Give Flask a moment to bind the port before Vite tries to proxy to it
sleep 1

# ── Start frontend ────────────────────────────────────────────────────────
echo "⚡  Starting Vite frontend on http://localhost:5173 …"
(cd "$REPO_ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "════════════════════════════════════════════════════════"
echo "  OmniFlow dev mode ready!"
echo ""
echo "  Testing (localhost):  http://localhost:5173"
echo "  Backend API:          http://127.0.0.1:5001"
echo ""
echo "  Both environments share the same backend rules."
echo "  Press Ctrl+C to stop both servers."
echo "════════════════════════════════════════════════════════"
echo ""

# Wait for either process to exit
wait
