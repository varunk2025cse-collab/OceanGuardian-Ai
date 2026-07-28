# OceanGuardian AI

**A marine safety and fisheries intelligence platform** — GPS tracking,
offline-first sync, an AI-assisted safety engine, emergency SOS, incident
management, and a rescue operations dashboard, built to help fishermen,
their families, rescue operators, and coastal authorities.

## Who this helps

- **Fishermen** get offline-first GPS tracking (works with zero signal at
  sea), one-touch SOS with an emergency-type taxonomy, live weather, and a
  transparent safety-state readout — never a false "you're safe."
- **Family members** see a linked fisherman's last known location, safety
  state, and incident status — with clear LIVE/RECENT/LAST_KNOWN/STALE/
  UNKNOWN labeling, never a stale point shown as live.
- **Rescue operators** get a live fleet map, full SOS/incident lifecycle
  management with an audit trail, real analytics, and an AI panel that
  answers operational questions from live authorized data.
- **Coastal authorities** get a system designed around one principle:
  safety-critical paths (manual SOS) never depend on AI, weather, or
  notification providers being available.

**Current status:** see `docs/GOD_MODE_STATUS.md` for the authoritative,
test-verified module-by-module status, and
`docs/RELEASE_READINESS_REPORT.md` for the release recommendation.

## Architecture

```
Fisherman App (Flutter) ── GPS + offline SQLite outbox ── Sync Engine
                                                                │
Family Portal (same app, role-switched) ──────┐               │
                                                ▼               ▼
                                        OceanGuardian Backend (FastAPI)
                                                │
        ┌───────────────┬───────────────┬──────┴────────┬──────────────┐
        ▼               ▼               ▼               ▼              ▼
   Tracking &      Weather          Safety Engine    Incident       AI Layer
   Location Freshness (live,   (deterministic,   Engine (8-state  (template by
   (client_uuid   Open-Meteo)  rule-based)        machine, audit  default, real
   idempotent)                                    trail)          LLM optional)
        │                                                │              │
        └────────────────────────┬───────────────────────┴──────────────┘
                                  ▼
                     Notification Engine (simulation by
                     default, real SMS optional) + PostgreSQL
                                  │
                    ┌─────────────┴──────────────┐
                    ▼                              ▼
          Rescue Dashboard (React)        Future: IoT Device Gateway
          live fleet map, incidents,      (interface defined, no
          AI panel, real analytics        hardware — deliberately
                                           out of scope, see
                                           docs/V2_ARCHITECTURE.md)
```

Full detail: `docs/V2_ARCHITECTURE.md`, `docs/V2_CORE_IMPLEMENTATION_PLAN.md`,
and the per-module docs listed below.

## How to run

### One-command demo (recommended first step)

```bash
bash scripts/demo_mode.sh        # or scripts\demo_mode.ps1 on Windows
```

Starts the backend + dashboard against an isolated demo database, seeds a
demo fisherman/family/operator, and drives a full real scenario (trip →
GPS → live weather → SOS → incident → operator acknowledgement) through
the actual API. See `docs/DEMO.md` for exactly what it does and the
verified output from the last run.

### Manual local development

**Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # edit DATABASE_URL and JWT_SECRET_KEY at minimum

alembic upgrade head        # create/migrate the database (Postgres) —
                             # or just start the app once against SQLite,
                             # which auto-creates tables for local dev
python seed.py               # reference data (harbors, weather, market, schemes)

uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs · Health: http://localhost:8000/health

**Rescue Dashboard**
```bash
cd rescue-dashboard
npm install
npm run dev    # http://localhost:3000  (proxies /api → localhost:8000)
```

**Mobile app** (needs a device/emulator)
```bash
cd mobile
flutter pub get
flutter run --dart-define=OG_API_BASE_URL=http://10.0.2.2:8000   # Android emulator
```

### Docker Compose

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD and JWT_SECRET_KEY — compose
                        # will refuse to start without them (see docker-compose.yml)
cd rescue-dashboard && npm install && npm run build && cd ..
docker compose up --build
```

### Tests

```bash
cd backend && python -m pytest tests/ -q          # 236 passed, 2 honestly skipped
cd mobile && flutter analyze --no-fatal-infos --fatal-warnings && flutter test
cd rescue-dashboard && npm run build
```

Full test strategy, including the 2 skipped tests and why, in `docs/TESTING.md`.
CI runs all of the above automatically — `docs/CI.md`.

## Environment variables

See `backend/.env.example` — organized into REQUIRED / OPTIONAL / DEMO-ONLY
/ PRODUCTION-ONLY sections. Nothing is required beyond a database URL and a
JWT secret; every external integration (weather, AI, notifications) has a
safe, honest, fully-functional default that never fakes a real provider.

## Simulation vs. real integrations

| Integration | Default | Real path |
|---|---|---|
| Weather | **Real** (Open-Meteo, free, no key, verified live in this repo's tests) | Same — `WEATHER_PROVIDER=simulated` opts into synthetic data instead |
| AI explanations | Template (deterministic, always works) | `AI_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` — implemented, **not verified** (no credentials in development) |
| SMS/push notifications | Simulation (logged + recorded, never claims real delivery) | `NOTIFICATION_PROVIDER=twilio` + Twilio credentials — implemented, **not verified** |
| GPS | **Real** (device GPS via `geolocator`) | N/A — always real |
| IoT/hardware | **Not built** — deliberately out of scope. `LocationPing.source` is the seam for `IOT_DEVICE`/`SATELLITE` later. | — |

Full inventory with test evidence: `docs/GOD_MODE_STATUS.md` §16.

## Security model

- JWT auth, bcrypt password hashing, role-based access control (fisherman/
  family/operator).
- Public self-registration cannot create an operator account (a real
  vulnerability found and fixed in this repo's audit — see
  `docs/V1_AUDIT.md`).
- Location/safety/incident data access is authorization-checked per
  request: a family member sees only a fisherman they're explicitly
  linked to; never anyone else.
- Rate limiting on login/register (never on SOS — see
  `backend/app/core/rate_limit.py`).
- No secrets committed; `docker-compose.yml` refuses to start without
  `POSTGRES_PASSWORD`/`JWT_SECRET_KEY` set.

Full detail: `docs/SECURITY.md`.

## Known limitations

- Real LLM (Anthropic) and real SMS (Twilio) provider paths are
  implemented but unverified — no credentials exist in this development
  environment. The system is fully functional without them.
- No automated retry job for a failed notification yet (the failure is
  recorded, not silently dropped, but isn't automatically re-driven).
- No CI-enforced dependency vulnerability scanning yet.
- The `mobile/` app has no `android/`/`ios/` platform folders yet — run
  `flutter create .` before building a real device binary.
- Fleet-wide safety evaluation isn't batched — fine at current scale, would
  need optimization for a large fleet (hundreds of concurrent active trips).

Full list with context: `docs/GOD_MODE_STATUS.md` §15, and
`docs/RELEASE_READINESS_REPORT.md`.

## Documentation index

| Doc | Covers |
|---|---|
| `docs/V1_AUDIT.md` | Original codebase audit — what existed, what was broken, what was fake |
| `docs/V2_ARCHITECTURE.md`, `docs/V2_CORE_IMPLEMENTATION_PLAN.md` | Target architecture and phased build plan |
| `docs/GOD_MODE_STATUS.md` | Module-by-module completion status, test-verified |
| `docs/RELEASE_READINESS_REPORT.md` | Final release recommendation |
| `docs/SAFETY_STATE_ENGINE.md` | Deterministic safety scoring |
| `docs/WEATHER_INTELLIGENCE.md` | Live weather provider |
| `docs/AI_ARCHITECTURE.md`, `docs/AI_TOOLS.md` | AI explainability + Rescue AI panel |
| `docs/SOS_ARCHITECTURE.md` | Emergency taxonomy, offline-first trigger |
| `docs/INCIDENT_ENGINE.md` | 8-state incident lifecycle + audit trail |
| `docs/NOTIFICATIONS.md` | Notification provider abstraction |
| `docs/SECURITY.md` | Security posture, fixed findings, known gaps |
| `docs/CI.md` | Continuous integration pipeline |
| `docs/DEMO.md` | One-command demo scenario |
| `docs/TESTING.md` | Test strategy across all three apps |
| `docs/DEPLOYMENT.md` | Deployment instructions |
