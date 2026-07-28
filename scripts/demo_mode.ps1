# OceanGuardian AI — one-command Demo Mode (Windows PowerShell)
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

param(
    [int]$ApiPort = 8000,
    [int]$DashboardPort = 3000
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RootDir "backend"
$DashboardDir = Join-Path $RootDir "rescue-dashboard"
$PidFile = Join-Path $RootDir ".demo_mode.pids"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " OceanGuardian AI - DEMO MODE" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "Never uses production secrets. Never creates insecure credentials"
Write-Host "outside this explicit demo run. See docs/DEMO.md for full detail."
Write-Host "=================================================================="

# ---- 1. Verify dependencies --------------------------------------------
$PythonBin = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonBin)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonBin = "python"
    } else {
        Write-Error "No backend/.venv and no 'python' on PATH. Set up the backend venv first (see README.md)."
        exit 1
    }
}
Write-Host "Using Python: $PythonBin"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "node not found on PATH."
    exit 1
}

# ---- 2/3. Demo database + env ------------------------------------------
Write-Host ""
Write-Host "Demo database: backend\demo_mode.db (isolated from your regular dev DB)"

$env:DATABASE_URL = "sqlite:///./demo_mode.db"
if (-not $env:JWT_SECRET_KEY) {
    $env:JWT_SECRET_KEY = "demo-mode-$(Get-Date -UFormat %s)-not-for-production"
}
$env:ENVIRONMENT = "development"
$env:SEED_DEMO_DATA = "true"
$env:DEMO_MODE = "true"
$env:CORS_ORIGINS = "http://localhost:$DashboardPort,http://127.0.0.1:$DashboardPort"
# WEATHER_PROVIDER / NOTIFICATION_PROVIDER / AI_PROVIDER intentionally left
# at their defaults (open-meteo / simulation / template) unless already set
# in the calling shell.

Push-Location $BackendDir
try {
    Write-Host ""
    Write-Host "---- Installing backend dependencies (fast if already installed) ----"
    & $PythonBin -m pip install -q -r requirements.txt

    Write-Host ""
    Write-Host "---- Seeding reference data + demo operator account ----"
    & $PythonBin seed.py

    Write-Host ""
    Write-Host "---- Starting backend on port $ApiPort ----"
    $backendLog = Join-Path $RootDir ".demo_mode_backend.log"
    $proc = Start-Process -FilePath $PythonBin `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$ApiPort" `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" `
        -PassThru -WindowStyle Hidden
    $proc.Id | Out-File -FilePath $PidFile -Encoding utf8
    Write-Host "Backend PID $($proc.Id) (log: .demo_mode_backend.log)"

    Write-Host -NoNewline "Waiting for backend to become healthy"
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$ApiPort/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch {}
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 1
    }
    if ($healthy) { Write-Host " up." } else { Write-Warning "Backend did not report healthy within 30s — check $backendLog" }

    Write-Host ""
    Write-Host "---- Creating demo fisherman/family/boat/trip/GPS trail/SOS/incident ----"
    $env:DEMO_API_BASE_URL = "http://localhost:$ApiPort"
    & $PythonBin demo_seed.py
} finally {
    Pop-Location
}

# ---- Dashboard (best-effort) --------------------------------------------
Write-Host ""
$dashboardStarted = $false
try {
    Push-Location $DashboardDir
    if (-not (Test-Path (Join-Path $DashboardDir "node_modules"))) {
        Write-Host "---- Installing dashboard dependencies ----"
        npm install | Out-Null
    }
    Write-Host "---- Starting rescue dashboard on port $DashboardPort ----"
    $dashboardLog = Join-Path $RootDir ".demo_mode_dashboard.log"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev", "--", "--port", "$DashboardPort" `
        -WorkingDirectory $DashboardDir `
        -RedirectStandardOutput $dashboardLog -RedirectStandardError "$dashboardLog.err" `
        -WindowStyle Hidden | Out-Null
    $dashboardStarted = $true
} catch {
    Write-Warning "Could not start the dashboard automatically: $_"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " DEMO MODE READY" -ForegroundColor Green
Write-Host "=================================================================="
Write-Host "Backend API:         http://localhost:$ApiPort"
Write-Host "API docs (Swagger):  http://localhost:$ApiPort/docs"
Write-Host "System info/mode:    http://localhost:$ApiPort/api/v1/system-info"
if ($dashboardStarted) {
    Write-Host "Rescue Dashboard:    http://localhost:$DashboardPort  (may take a few seconds to finish starting)"
} else {
    Write-Host "Rescue Dashboard:    run manually -> cd rescue-dashboard; npm install; npm run dev"
}
Write-Host ""
Write-Host "Demo accounts:"
Write-Host "  Fisherman:  +911111000001 / Demo@1234"
Write-Host "  Family:     +911111000002 / Demo@1234"
Write-Host "  Operator:   +911234567890 / rescue123"
Write-Host ""
Write-Host "Mobile app (run separately, needs a device/emulator - not started"
Write-Host "by this script):"
Write-Host "  cd mobile"
Write-Host "  flutter run --dart-define=OG_API_BASE_URL=http://10.0.2.2:$ApiPort   # Android emulator"
Write-Host ""
Write-Host "To stop the demo backend: Stop-Process -Id (Get-Content '$PidFile')"
Write-Host "(the dashboard dev server, if started, must be stopped separately)"
Write-Host "=================================================================="
