#!/usr/bin/env bash
# OceanGuardian AI — one-command Demo Mode (Bash / Git Bash / WSL / Linux / macOS)
#
# Starts the backend against a dedicated demo SQLite database, seeds
# reference data + a demo operator account (SEED_DEMO_DATA=true), creates a
# demo fisherman/family/boat/trip/GPS-trail/SOS/incident via real API calls
# (backend/demo_seed.py — not raw DB inserts, so it proves the real code
# paths work), and prints every access URL + credential.
#
# This is DEMO MODE: SEED_DEMO_DATA=true and DEMO_MODE=true are never safe
# in a real deployment — see docs/SECURITY.md. The backend's
# /api/v1/system-info endpoint reports demo_mode=true while this is
# running, which both the mobile app and rescue dashboard surface as a
# persistent "DEMO / SIMULATION MODE" banner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
DASHBOARD_DIR="$ROOT_DIR/rescue-dashboard"
PID_FILE="$ROOT_DIR/.demo_mode.pids"

API_PORT="${DEMO_API_PORT:-8000}"
DASHBOARD_PORT="${DEMO_DASHBOARD_PORT:-3000}"

echo "=================================================================="
echo " OceanGuardian AI — DEMO MODE"
echo "=================================================================="
echo "Never uses production secrets. Never creates insecure credentials"
echo "outside this explicit demo run. See docs/DEMO.md for full detail."
echo "=================================================================="

# ---- 1. Verify dependencies -------------------------------------------
command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 || {
  echo "ERROR: python3 not found on PATH." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not found on PATH." >&2; exit 1; }
PYTHON_BIN="python"
command -v python3 >/dev/null 2>&1 && PYTHON_BIN="python3"

if [ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/Scripts/python.exe"   # Windows venv
elif [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"            # POSIX venv
fi
echo "Using Python: $PYTHON_BIN"

# ---- 2/3. Demo database + env ------------------------------------------
DEMO_DB="$BACKEND_DIR/demo_mode.db"
echo "Demo database: $DEMO_DB (isolated from your regular dev DB — never touches oceanguardian.db)"

export DATABASE_URL="sqlite:///./demo_mode.db"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-demo-mode-$(date +%s)-not-for-production}"
export ENVIRONMENT="development"
export SEED_DEMO_DATA="true"
export DEMO_MODE="true"
export CORS_ORIGINS="http://localhost:${DASHBOARD_PORT},http://127.0.0.1:${DASHBOARD_PORT}"
# WEATHER_PROVIDER / NOTIFICATION_PROVIDER / AI_PROVIDER intentionally left
# at their defaults (open-meteo / simulation / template) unless already set
# in the calling shell — real weather stays real when reachable; AI/
# notifications stay honestly simulated unless you've exported real
# credentials (ANTHROPIC_API_KEY, TWILIO_*) before running this script.

cd "$BACKEND_DIR"
echo ""
echo "---- Installing backend dependencies (fast if already installed) ----"
"$PYTHON_BIN" -m pip install -q -r requirements.txt

echo ""
echo "---- Seeding reference data + demo operator account ----"
"$PYTHON_BIN" seed.py

echo ""
echo "---- Starting backend on port $API_PORT ----"
# `< /dev/null` + `disown`: fully detaches the child from this script's
# stdin/stdout pipe. Without this, Git Bash/MSYS on Windows can keep the
# whole script (and anything piping its output, e.g. `| tail`) blocked
# waiting for the background process to exit, even though its own
# stdout/stderr are redirected to a file.
"$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" < /dev/null > "$ROOT_DIR/.demo_mode_backend.log" 2>&1 &
BACKEND_PID=$!
disown "$BACKEND_PID" 2>/dev/null || true
echo "$BACKEND_PID" > "$PID_FILE"
echo "Backend PID $BACKEND_PID (log: .demo_mode_backend.log)"

echo -n "Waiting for backend to become healthy"
for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://localhost:${API_PORT}/health"; then
    echo " — up."
    break
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "---- Creating demo fisherman/family/boat/trip/GPS trail/SOS/incident ----"
DEMO_API_BASE_URL="http://localhost:${API_PORT}" "$PYTHON_BIN" demo_seed.py

# ---- Dashboard (best-effort) --------------------------------------------
echo ""
if [ -d "$DASHBOARD_DIR/node_modules" ] || (cd "$DASHBOARD_DIR" && npm install --silent >/dev/null 2>&1); then
  echo "---- Starting rescue dashboard on port $DASHBOARD_PORT ----"
  cd "$DASHBOARD_DIR"
  npm run dev -- --port "$DASHBOARD_PORT" < /dev/null > "$ROOT_DIR/.demo_mode_dashboard.log" 2>&1 &
  disown "$!" 2>/dev/null || true
  cd "$ROOT_DIR"
  echo "Dashboard starting in the background (log: .demo_mode_dashboard.log)"
else
  echo "Dashboard dependencies could not be installed automatically —"
  echo "run manually: cd rescue-dashboard && npm install && npm run dev"
fi

cat <<EOF

==================================================================
 DEMO MODE READY
==================================================================
Backend API:        http://localhost:${API_PORT}
API docs (Swagger):  http://localhost:${API_PORT}/docs
System info/mode:    http://localhost:${API_PORT}/api/v1/system-info
Rescue Dashboard:    http://localhost:${DASHBOARD_PORT}  (may take a few seconds to finish starting)

Demo accounts:
  Fisherman:  +911111000001 / Demo@1234
  Family:     +911111000002 / Demo@1234
  Operator:   +911234567890 / rescue123

Mobile app (run separately, needs a device/emulator — not started by
this script):
  cd mobile
  flutter run --dart-define=OG_API_BASE_URL=http://10.0.2.2:${API_PORT}   # Android emulator
  # or use your machine's LAN IP instead of 10.0.2.2 for a physical device

To stop the demo backend: kill \$(cat "$PID_FILE")
(the dashboard dev server, if started, must be stopped separately —
 Ctrl+C in its terminal, or find it via its logged port)
==================================================================
EOF
