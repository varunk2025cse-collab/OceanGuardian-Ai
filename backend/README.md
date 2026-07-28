# OceanGuardian AI — Backend (FastAPI MVP)

Real, tested FastAPI service: JWT auth, offline GPS sync, SOS alerts,
weather alerts, market prices, government schemes, family tracking.

19 endpoints. Verified end-to-end (see "Verification" below) against both
SQLite and a real PostgreSQL 16 database — every flow in this README has
actually been executed, not just written.

## Step 1 — Install

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2 — Configure

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL to your real Postgres instance,
# and JWT_SECRET_KEY to a long random string (never reuse the example value).
```

## Step 3 — Create the database

Two ways to get the schema in place — pick one:

**Option A (recommended for first run): let the app create it.**
The app calls `Base.metadata.create_all()` on startup (see `app/main.py`),
so simply starting the server against an empty database is enough for the MVP.

**Option B: run the hand-inspectable SQL directly.**
```bash
createdb oceanguardian
psql -d oceanguardian -f schema.sql
```
`schema.sql` is generated FROM the SQLAlchemy models (`python generate_schema_sql.py > schema.sql`),
so it can never silently drift from the actual code — regenerate it after
any model change.

## Step 4 — Seed reference data (weather/market/schemes start empty otherwise)

```bash
python seed.py
```

## Step 5 — Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: http://localhost:8000/docs
Health check: http://localhost:8000/health

## Verification

This isn't just written, it's been run. From this directory:

```bash
pip install -r requirements.txt
python -m pytest tests/test_smoke.py -v
```

`tests/test_smoke.py` is an end-to-end test (not a mock) that boots the
real FastAPI app and walks the full MVP flow: register fisherman → login →
offline GPS batch sync (including a duplicate-resend idempotency check) →
SOS trigger (including a button-mash idempotency check) → SOS status
update → weather alerts filtered by GPS position → market prices →
government schemes → family account registration → family→fisherman
linking → family status dashboard read. It passes against SQLite by
default; point `DATABASE_URL` at Postgres to run the identical test there.

## Project layout

```
app/
  main.py            FastAPI app, router wiring, CORS, table creation
  config.py          Settings loaded from .env (pydantic-settings)
  database.py        SQLAlchemy engine/session
  core/
    security.py      Password hashing (bcrypt) + JWT issue/verify
    deps.py           get_current_user dependency
  models/            SQLAlchemy ORM models (one file per entity)
  schemas/           Pydantic request/response models
  routers/           One router per feature area
  services/
    geo.py            Haversine distance (weather zone matching)
    sos_service.py    SOS notification fan-out (logs for now; swap in
                       real SMS/push/Coast-Guard-webhook integration later)
schema.sql            Generated PostgreSQL DDL (see generate_schema_sql.py)
seed.py                Reference-data seeding script
tests/test_smoke.py    End-to-end smoke test
```

## API surface (19 endpoints)

| Area | Endpoint | Notes |
|---|---|---|
| Auth | `POST /api/v1/auth/register` | Fisherman or family role |
| Auth | `POST /api/v1/auth/login` | |
| Auth | `POST /api/v1/auth/refresh` | |
| Auth | `GET /api/v1/auth/me` | |
| Location | `POST /api/v1/locations/ping` | Single live GPS fix |
| Location | `POST /api/v1/locations/sync` | Offline batch upload, idempotent |
| Location | `GET /api/v1/locations/me/latest` | |
| Location | `GET /api/v1/locations/me/history` | |
| SOS | `POST /api/v1/sos/trigger` | Idempotent on `client_uuid` |
| SOS | `GET /api/v1/sos/active` | Rescue-dashboard feed |
| SOS | `PATCH /api/v1/sos/{id}/status` | Acknowledge / resolve / false alarm |
| SOS | `GET /api/v1/sos/me/history` | |
| Weather | `GET /api/v1/weather/active` | Optional `?lat=&lon=` zone filter |
| Market | `GET /api/v1/market/prices` | Optional `?region=&species=&on_date=` |
| Schemes | `GET /api/v1/schemes/` | Optional `?region=&category=` |
| Family | `POST /api/v1/family/link` | Link a family account to a fisherman |
| Family | `GET /api/v1/family/status` | Last position + active-SOS per linked fisherman |
| Health | `GET /`, `GET /health` | |

Full request/response shapes: run the server and open `/docs` (auto-generated
from the Pydantic schemas — always in sync with the real code).

## Hardening before a real launch (intentionally out of scope for this MVP)

- Replace `Base.metadata.create_all()` with Alembic migrations (the
  dependency is already in `requirements.txt`).
- Add an `operator`/`coast_guard` role check on `PATCH /sos/{id}/status`
  before exposing a Rescue Dashboard to non-fisherman users.
- Real SMS/push notification provider in `sos_service.notify_emergency_contacts`.
- Rate limiting on `/auth/login` and `/sos/trigger`.
- Move JWT signing key + DB credentials to a real secrets manager.
