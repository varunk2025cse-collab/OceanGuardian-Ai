# OceanGuardian AI — V1.0 Audit

**Audit date:** 2026-07-25
**Method:** Full read-only inspection of `backend/`, `mobile/`, `rescue-dashboard/`,
root-level documentation, and infra config (`docker-compose.yml`, `nginx.conf`).
**Purpose:** Establish ground truth before starting V2.0 work. Root-level status
docs (`PROJECT_COMPLETION_REPORT.md`, `PHASE*.md`, etc.) make broad "100%
complete / production ready" claims that this audit repeatedly finds are not
supported by the code. This document is the source of truth going forward;
where it conflicts with an older doc, trust this one (and re-verify against
the code if more time has passed since the audit date above).

All file paths are relative to the repo root
(`c:\Users\lenovo\Downloads\oceanguardian-version 1.0`) unless noted otherwise.

---

## 1. Existing Architecture

```
                    ┌─────────────────────┐
                    │   Flutter Mobile App │  (fisherman + family, role-switched tabs)
                    │   mobile/lib/        │
                    └──────────┬───────────┘
                               │ HTTP (http package), JWT bearer
                    ┌──────────▼───────────┐        ┌──────────────────────┐
                    │   FastAPI Backend     │◄───────┤  React Rescue        │
                    │   backend/app/        │  HTTP  │  Dashboard (operator)│
                    │  routers/ (v1 + v2)   │        │  rescue-dashboard/   │
                    │  services/ (v2 only)  │        └──────────────────────┘
                    │  models/ (SQLAlchemy) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ PostgreSQL (prod) /   │
                    │ SQLite (dev/test)     │
                    └───────────────────────┘

  Infra: docker-compose.yml defines db (postgres:16-alpine), api (backend
  Dockerfile), dashboard (nginx serving the built React app). nginx.conf
  reverse-proxies /api/ to the api container and serves the SPA otherwise.
```

**Backend** — Python 3.12, FastAPI 0.115.0, SQLAlchemy 2.0.35 (declarative
ORM), Alembic 1.13.2 migrations, Pydantic v2 schemas, JWT auth via
`python-jose` + `bcrypt`. Two API generations coexist:
- **v1** (`app/routers/*.py`, excluding `v2/`): auth, location, sos, weather,
  market, schemes, family, boats, trips, harbors, risk, admin. Business logic
  is embedded directly in route handlers — no dedicated v1 service layer.
- **v2** (`app/routers/v2/*.py`, "Phase 5 Intelligence Layer"): harbor,
  boat_health, checkin, escalation, family_portal, risk_prediction, analytics.
  These routers are thin and delegate to `app/services/*.py` classes — a
  materially better-organized pattern than v1, though several v2 services
  also define their own Pydantic schemas inline instead of in `app/schemas/`,
  blurring that boundary.

**Mobile** — Flutter/Dart, no state-management framework (no
Provider/Riverpod/Bloc/GetX). Architecture is a flat set of singleton
services (`AuthService.instance`, `LocationService.instance`,
`SosService.instance`, `SyncService.instance`, `LocalDbService.instance`,
`ReferenceDataService.instance`, `ApiClient.instance`) called directly from
`StatefulWidget` screens. No repository layer, no DI container. Local
persistence via `sqflite` (offline outbox + generic cache table) and
`shared_preferences` (session).

**Rescue dashboard** — React 18.3.1 + Vite 5.4.8 + Tailwind CSS, Leaflet for
mapping, plain `axios` for HTTP, `useState`/Context for state (no
Redux/Zustand). Pages are polled every 20-60s via a custom `usePolling` hook
rather than websockets/SSE.

---

## 2. Existing Features (by module — real / partial / stubbed / fake)

| Feature | Status | Notes |
|---|---|---|
| Auth (register/login/refresh/me) | **Real** | JWT, bcrypt; see §10 for the critical role-assignment bug |
| Offline GPS capture + sync (mobile) | **Real** | SQLite outbox (`pending_locations`), `client_uuid` idempotency, batch POST `/locations/sync`, connectivity-triggered + 30s-polled sync |
| Offline SOS trigger + retry (mobile) | **Real** | Local-first write to `pending_sos` before any network call; best-effort immediate send; retried by `SyncService`, prioritized first in every sync cycle |
| SOS API + status transitions (backend) | **Real**, role-gated | Fisherman can only self-resolve as `false_alarm`; operator can set any status; family blocked |
| Rescue dashboard — SOS list/detail/map/fishermen | **Real**, live REST-backed | Polled, not push-based |
| Trip lifecycle | **Backend-only** | Full API exists (`/trips/start|end|active|history`) but **mobile has zero trip model, screen, or service** — GPS tracking starts on login, not on trip start, so there is no trip-scoped trail today |
| Weather screen (mobile) | **Real wiring, fake data source** | Calls real `/weather/active` endpoint with cache-first fallback; but the backend table is seed-only, see §6 |
| Market prices / govt schemes (mobile + backend) | **Real wiring, static catalog** | Read-only, seed-populated, no update pipeline or write endpoint |
| Family connectivity | **Partial** | Link/unlink/status endpoints and mobile `FamilyScreen` are real; but the "notify family" side (§12) never actually sends anything |
| "AI Marine Copilot" | **Vaporware** | DB tables (`copilot_sessions`, `copilot_conversations`) exist with fields implying a voice+LLM pipeline; **no router, service, or LLM call exists anywhere** |
| Risk Prediction Engine | **Not ML** | `RiskPredictionService.calculate_risk_score` is a hand-coded weighted sum of 8 factors; `model_version="rule_based_v1.0"` and `prediction_confidence=0.85` are hardcoded literals, not computed values |
| Analytics — risk zones / boat health | **Partly hardcoded fake data** | `high_risk_zones` is a fixed 2-item list; `overdue_maintenance_boats=2` is a constant; risk-tier trip counts are fixed percentages of SOS count, not derived from actual per-trip risk |
| Notifications (push/SMS/email) | **Fully stubbed** | The entire dispatch mechanism is one `logger.warning()` call in `sos_service.py`; `FamilyNotification` rows are never created by any code path; escalation "notified" booleans are set without any message ever being sent |
| Background automation (escalation, missed check-ins) | **No scheduler exists** | No Celery/APScheduler/cron anywhere in the backend; all "automatic" processing requires an operator to manually call an endpoint (`/check-ins/process`, `/escalations/auto-escalate`, etc.) |
| IoT / device telemetry | **None** | No MQTT, no device gateway, no sensor-ingestion protocol; boat health/fuel data is manually POSTed by the fisherman |
| Mobile voice assistant | **UI copy only** | No `speech_to_text`/`flutter_tts` package; only aspirational strings ("Voice-friendly") in code comments; project's own `PHASE4_COMPLETE.md` lists it under "Future" |
| Mobile trip / boat-health / harbor screens | **Do not exist** | No corresponding screen, model, or service in `mobile/lib` despite root docs claiming completion |
| Rescue dashboard Analytics page | **Mostly mocked** | 5 charts are literal `ChartPlaceholder` components (no chart library used at all); "Avg Response Time" and trend arrows are hardcoded; Export CSV/PDF buttons have no handlers |
| Incident state machine | **Simplified** | Implemented as 4 states (`active/acknowledged/resolved/false_alarm`), not the richer lifecycle a mature ops model would use; `RiskIncident` (a proper timeline/audit table) exists in the schema but nothing reads or writes it |
| Multilingual support (mobile) | **Broken as committed** | ARB files (English + Tamil) are complete and wired via `AppLocalizations`, but `pubspec.yaml` is missing `generate: true` and there's no `l10n.yaml` — the codegen step the whole app depends on will not run, so **the app does not currently compile** |

---

## 3. Existing Database Entities

**v1 tables** (`backend/app/models/*.py`, excluding `phase5.py`):

| Table | Key fields |
|---|---|
| `users` | id, phone_number (unique), password_hash, full_name, role (fisherman/family/operator), boat_name, boat_registration_number, home_harbor, preferred_language, emergency_contact_name/phone, last_sync_at, is_active |
| `family_links` | fisherman_id, family_user_id, relation (unique pair) |
| `location_pings` | client_uuid (unique), user_id, trip_id, lat/lon, accuracy, speed, heading, recorded_at, synced_at |
| `sos_alerts` | client_uuid, user_id, trip_id, alert_type, lat/lon, accuracy, battery_level, message, status (active/acknowledged/resolved/false_alarm), priority, rescue_notes, acknowledged_by/at, resolved_by/at, resolved_note, triggered_at |
| `weather_alerts` | title, description, hazard_type, severity, region, center lat/lon, radius_km, valid_from/until, source |
| `market_prices` | species, market_name, harbor_region, price_per_kg, currency, price_date |
| `govt_schemes` | title, category, region, description, eligibility, how_to_apply, contact_info, is_active |
| `boats` | owner_id, name, registration_number (unique), color, length_meters, engine_type/hp, fuel_capacity_liters, safety_equipment, is_active |
| `trips` | user_id, boat_id, status (active/completed/emergency/cancelled — plain string, not enum), start/end_time, estimated_return_at, start lat/lon, destination, notes |

**v2 / "Phase 5" tables** (all in `backend/app/models/phase5.py`):

`copilot_sessions`, `copilot_conversations` (unused — see §2), `risk_predictions`,
`risk_incidents` (unused — see §2), `risk_model_metrics` (unused — nothing
writes to it), `checkin_logs`, `checkin_alerts`, `check_in_schedules`,
`check_in_requests`, `missed_check_ins`, `safety_escalations`,
`operator_action_logs`, `harbors`, `harbor_reviews`, `harbor_visits`,
`boat_fuel_logs`, `boat_maintenance`, `boat_health_status`,
`fuel_predictions`, `family_portal_access`, `family_safety_events`,
`family_notifications` (unused — see §2), `analytics_sos_metrics`,
`analytics_trip_metrics`, `analytics_risk_metrics`, `analytics_user_engagement`.

**Migrations:** 6 linear Alembic revisions (001 baseline → 006 week3
services), `alembic/versions/`. Note: `app/main.py` also calls
`Base.metadata.create_all()` plus a custom `ensure_compatible_schema()`
shim on every startup that auto-`ALTER TABLE`s missing columns, but **only
against SQLite** — Postgres deployments must run `alembic upgrade head`
explicitly or schema drift will occur silently.

Several models (`user.py`, `location.py`, `sos.py`, `boat.py`, `trip.py`,
`weather_alert.py`) override `__init__` to silently remap legacy/alternate
kwarg names — pragmatic but fragile; worth documenting or removing in V2.

---

## 4. Existing APIs

**v1**, prefix `/api/v1`:

| Router | Endpoints |
|---|---|
| auth | POST `/auth/register`, POST `/auth/login`, POST `/auth/refresh`, GET `/auth/me` |
| location | POST `/locations/ping`, POST `/locations/sync`, GET `/locations/me/latest`, GET `/locations/me/history` |
| sos | POST `/sos/trigger`, GET `/sos/active`, PATCH `/sos/{id}/status`, GET `/sos/me/history` |
| weather | GET `/weather/active` |
| market | GET `/market/prices` |
| schemes | GET `/schemes/` |
| family | POST `/family/link`, DELETE `/family/unlink/{fisherman_id}`, GET `/family/status` |
| boats | POST `/boats/`, GET `/boats/`, GET `/boats/{id}`, PATCH `/boats/{id}` |
| trips | POST `/trips/start`, POST `/trips/end`, GET `/trips/active`, GET `/trips/history` |
| harbors | GET `/harbors/`, GET `/harbors/nearest` |
| risk | GET `/risk/score` |
| admin (operator-only) | GET `/admin/stats`, GET `/admin/sos`, GET `/admin/sos/{id}`, PATCH `/admin/sos/{id}/status`, GET `/admin/fishermen`, GET `/admin/fishermen/{id}/locations` |

**v2 "Phase 5 Intelligence Layer"**, prefix `/api/v2`:

| Router | Endpoints |
|---|---|
| harbor | POST `/harbor/create`, GET `/harbor/{id}`, GET `/harbor/`, POST `/harbor/nearest`, POST `/harbor/emergency-harbor`, POST `/harbor/{id}/review`, GET `/harbor/{id}/reviews` |
| boat_health | POST `/boat-health/fuel-log`, GET `/boat-health/{id}/fuel-summary`, POST `/boat-health/maintenance`, GET `/boat-health/{id}/maintenance-due`, GET `/boat-health/{id}/health-score`, POST `/boat-health/{id}/update-engine-hours` |
| checkin | GET `/check-ins/me`, POST `/check-ins/respond`, GET `/check-ins/missed`, POST `/check-ins/monitor`, POST `/check-ins/schedule`, POST `/check-ins/respond-scheduled`, POST `/check-ins/escalate`, POST `/check-ins/process` |
| escalation | GET `/escalations/active`, GET `/escalations/{id}`, POST `/escalations/{id}/acknowledge`, POST `/escalations/{id}/resolve`, GET `/escalations/{id}/action-logs`, POST `/escalations/auto-escalate`, POST `/escalations/auto-upgrade` (note: module docstring references a `GET /escalations/operator/logs` that is not actually implemented) |
| family_portal | GET `/family/dashboard`, GET `/family/fisherman/{id}/safety-status`, GET `/family/fisherman/{id}/timeline`, POST `/family/notifications/{id}/mark-read`, GET `/family/notifications`, GET `/family/alerts` |
| risk_prediction | GET `/risk/current/{fisherman_id}`, GET `/risk/trip/{trip_id}`, GET `/risk/boats/high-risk`, POST `/risk/recalculate` |
| analytics | GET `/analytics/overview`, GET `/analytics/sos-trends`, GET `/analytics/response-times`, GET `/analytics/active-boats`, GET `/analytics/risk-zones`, GET `/analytics/harbor-usage`, GET `/analytics/boat-health` |

**Root:** GET `/`, GET `/health` (unauthenticated, does a live `SELECT 1`).

No "AI Marine Copilot" router exists despite being advertised in the FastAPI
app description string.

---

## 5. Existing User Roles

Only **3 roles** exist: `fisherman`, `family`, `operator` (`UserRole` enum,
`backend/app/models/user.py`). The V2 target model calls for 8 (+ boat
owner, harbor officer, fisheries officer, NGO/relief org, system admin).

Enforcement:
- `backend/app/core/deps.py` provides `get_current_user`,
  `get_current_operator`, `get_current_fisherman` dependencies.
- v1 routers generally use these dependencies consistently.
- v2 routers largely **re-implement role checks inline**
  (`if current_user.role != "operator": raise HTTPException(403, ...)`)
  rather than reusing `core/deps.py` — functionally equivalent today but
  inconsistent and easy to get wrong on a new endpoint.
- **Critical gap**: registration lets the caller pick their own role with no
  authorization check at all — see §10.

---

## 6. Existing Integrations

**None are real external integrations.** Specifically:
- **Weather**: `WEATHER_PROVIDER=open-meteo` is set in config but **never
  read anywhere in the code**. All weather data comes from the
  `weather_alerts` table, populated only by `seed.py` (2 hardcoded sample
  alerts). No admin endpoint even exists to add new alerts — only direct DB
  writes could add real ones today.
- **Maps**: mobile uses raw OpenStreetMap tiles (`flutter_map`, no API key);
  dashboard uses Leaflet + public OSM tile servers. Fine for dev; OSM's usage
  policy discourages hitting `tile.openstreetmap.org` directly at
  production scale — a tile proxy or commercial provider would be needed.
- **SMS/Push/Email**: no provider SDK or credentials anywhere
  (no Twilio/SNS/FCM/APNs/SMTP config).
- **LLM/AI**: no OpenAI/Anthropic/any LLM SDK call anywhere in the codebase.
- **IoT/hardware**: none.

---

## 7. Existing Tests

- **Backend**: pytest 8.3.3 + pytest-asyncio, 13 files, ~4,174 lines under
  `backend/tests/`. Reasonable breadth — smoke test (register/login, GPS
  sync + idempotency, SOS trigger + idempotency, weather/risk/market/
  schemes/harbors reads, family link+status), Phase 2 feature/security-fix
  tests, one file per v2 service. No CI configuration exists anywhere in the
  repo (no `.github/workflows`, no other CI system) — tests are run
  manually only.
- **Mobile**: exactly one smoke test (`test/widget_test.dart`) that pumps
  the app and checks the splash screen renders. No tests for
  Location/Sos/Sync/LocalDb/ApiClient services, no mocking packages in
  `pubspec.yaml`. The flat-singleton architecture makes unit testing with
  fakes difficult without refactoring toward dependency injection first.
- **Dashboard**: zero test files, no test runner configured in
  `package.json`.

---

## 8. Existing Strengths

- **Mobile offline-first design is genuinely well-executed**, not just
  error-handling bolted on: local SQLite is the source of truth for
  writes (GPS, SOS) before any network call; reads (weather/market/
  schemes/family) are cache-first with explicit `fromCache`/`asOf` flags
  surfaced to the UI as "offline" badges; a dedicated `SyncService` runs
  connectivity-triggered + polled reconciliation with SOS prioritized
  first and per-item error isolation.
- **`client_uuid`-based idempotency** is consistently applied for both
  location pings and SOS alerts, both client- and server-side (unique
  constraint + dedupe-on-insert), which is exactly the right pattern for
  offline-first sync.
- **v2 service layer** (`app/services/*.py`) is a real, non-trivial
  business-logic layer with proper separation from routers — the
  escalation engine in particular (`escalation.py`) implements genuine
  multi-threshold auto-escalation logic with an audit trail
  (`OperatorActionLog`).
- **Backend config** is cleanly centralized via `pydantic-settings`
  (`app/config.py`) with no scattered `os.environ.get()` calls elsewhere.
- **SOS status transition security** already has one documented fix in
  place (fisherman can only self-resolve as false_alarm, not arbitrarily
  change status) — evidence the team has iterated on real security bugs
  before, not just added features.

---

## 9. Technical Debt

- **Dead code**: `mobile/lib/widgets/info_card.dart` and `large_button.dart`
  (a "Phase 4 widget library") are never imported by any screen.
  `rescue-dashboard/src/pages/{DashboardPage,LoginPage,SOSAlertsPage,
  MapPage,FishermenPage}.jsx` (5 files, ~401 lines) are orphaned — `App.jsx`
  only imports the `*Premium.jsx` variants.
- **Inconsistent service/schema boundary in v2**: several
  `app/services/*.py` files define their own Pydantic schemas inline
  instead of using `app/schemas/`.
- **Role-check duplication**: v2 routers inline role checks instead of
  reusing `core/deps.py` dependencies (§5).
- **Fragile `__init__` kwarg-remapping shims** on 6 models for
  legacy/alternate field names (§3) — undocumented, easy to break silently.
- **Untyped admin endpoint**: `PATCH /api/v1/admin/sos/{id}/status` accepts
  a raw `dict` body instead of a Pydantic schema; an invalid status value
  raises an uncaught `ValueError` → unhandled 500 instead of a clean 4xx.
- **Version drift**: `rescue-dashboard/package.json` says `0.2.0`, the
  dashboard footer says `v0.3.0`, `PHASE5_LAUNCH_STATUS.md` says `0.5.0`.
- **Root-level documentation sprawl**: ~30 markdown files at repo root
  (many overlapping "PHASE5_WEEK2_*" summaries) vs. a nearly-empty `docs/`
  folder — see §14 for the cleanup this implies.
- **Mobile build is not actually verified**: the README itself states the
  code "has not been compiled with the actual Flutter toolchain" — combined
  with the missing l10n codegen flag (§2) and absent `android/`/`ios/`
  folders, the project cannot currently be built as committed.

---

## 10. Security Weaknesses

1. **CRITICAL — Unauthenticated privilege escalation.**
   `backend/app/schemas/user.py` (`UserRegister.role` pattern
   `^(fisherman|family|operator)$`) + `backend/app/routers/auth.py`
   (`register()` sets `role=UserRole(payload.role)` directly from the
   request body with no authorization check) means **any anonymous caller
   can register with `"role": "operator"`** and immediately receive a valid
   operator JWT — full Rescue Dashboard / admin API access, no invite code
   or approval step required.
2. **Hardcoded default operator credentials auto-seeded in production.**
   `backend/seed.py` creates `+911234567890` / `rescue123` as an operator
   account; `backend/Dockerfile`'s CMD runs `seed.py` unconditionally on
   every container start, including the production image build.
3. **Hardcoded weak secrets committed in `docker-compose.yml`** (repo
   root): `POSTGRES_PASSWORD: oceanguardian` (matching the username) and
   `JWT_SECRET_KEY: change-this-in-production-to-a-64-char-random-string`
   — a placeholder-looking value that is nonetheless the literal value used
   if this compose file is deployed as-is.
4. **No rate limiting anywhere** — `/auth/login`, `/auth/register`,
   `/sos/trigger` are all unthrottled (brute-force and SOS-spam/DoS risk).
5. **CORS defaults to wildcard with credentials** — `backend/.env.example`
   sets `CORS_ORIGINS=*` while `allow_credentials=True` is also set in
   `app/main.py`; browsers reject this combination outright, but it's a
   configuration smell that should be tightened for any non-dev use
   (the compose file does correctly override to explicit dev origins).
6. **Mobile tokens stored in plaintext** `shared_preferences`
   (`mobile/lib/services/auth_service.dart`) — the project's own README
   flags this as a pre-launch blocker; no `flutter_secure_storage`
   dependency exists yet.
7. **No account lockout / password complexity** beyond a 6-character
   minimum, combined with no rate limiting — weak for an emergency/safety
   platform's auth surface.
8. **`python-jose`** (sole JWT library) is a lower-maintenance-velocity
   dependency historically associated with algorithm-confusion-class CVEs
   in the broader ecosystem; worth a dependency-risk review against `PyJWT`.
9. **Dashboard ships pre-filled demo credentials** directly in the login
   form UI (`+911234567890` / `rescue123` visible in both the input
   defaults and the footer text) — low severity but should not ship in a
   production build.
10. **Notification "sent" flags without actual dispatch** (§2/§12) is a
    safety-relevant gap: operators/family can see a `notified=True` flag
    when no message was ever sent, risking false confidence during a real
    emergency.
11. **Docker hardening gaps**: container runs as root (no `USER`
    directive), no `HEALTHCHECK`, single-stage build installs `gcc`/
    `libpq-dev` unnecessarily since `psycopg2-binary` ships prebuilt wheels.

SQL injection risk is low — all queries go through the SQLAlchemy ORM with
parameterized filters; the one raw-SQL code path (`ensure_compatible_schema`)
interpolates only developer-defined model column names, not user input.

---

## 11. Missing Functionality (vs. the V2 target)

- Trip lifecycle UI/model in the mobile app (backend API already exists —
  see §2, this is the single biggest and easiest-to-close gap)
- Real external weather provider integration (config key exists, unused)
- Real notification dispatch (push/SMS/email) — currently log-only
- Background job scheduler — nothing runs automatically today
- Any LLM/AI reasoning layer (AI Copilot, AI Rescue Assistant, MCP tools,
  AI-generated incident reports) — zero implementation, schema-only in one case
- IoT device gateway, telemetry ingestion, hardware simulator
- 5 of the 8 target user roles (boat owner, harbor officer, fisheries
  officer, NGO, system admin)
- Voice assistant / speech I/O in the mobile app
- Boat health and harbor-services screens in the mobile app
- Immutable incident timeline usage (`RiskIncident` table exists, unused)
- CI pipeline (none exists for any of the three codebases)
- Crew-level safety features (roster, check-in/out, wearables) — entirely absent

---

## 12. Duplicate Functionality

- 5 orphaned, unused React page components in `rescue-dashboard/src/pages/`
  duplicating the functionality of their `*Premium.jsx` replacements (§9).
- Inline role-check logic in v2 routers duplicating what `core/deps.py`
  already provides (§5/§9).
- Two unused mobile widget components (`info_card.dart`, `large_button.dart`)
  that duplicate UI patterns already implemented ad-hoc within screens.

---

## 13. Scalability Concerns

- **No background job runner** (Celery/APScheduler/cron) — as the system
  grows, manually-triggered "automatic" processing (escalation, missed
  check-ins) will not scale to real operational use; this needs to be a
  genuine scheduler, not a dashboard button.
- **SQLite/Postgres split relies on an ad-hoc schema-sync shim** that only
  runs against SQLite (`ensure_compatible_schema`) — Postgres deployments
  depend entirely on disciplined `alembic upgrade head` execution; no
  safety net if that's skipped.
- **No connection pooling configuration visible** in `app/database.py`
  beyond SQLAlchemy defaults — worth revisiting under real concurrent load.
- **No dependency lock file** (`requirements.txt` only, no
  `pip-compile`/`poetry.lock`) — builds are not fully reproducible, which
  matters more as more services/team members are added.
- **Dashboard polling (20-60s intervals) instead of push/websockets** —
  adequate at small scale, but SOS alerts are time-critical; this should be
  revisited if operator load grows (e.g. move to SSE/websockets in V2).
- **Analytics computed synchronously per-request** in v2 services — fine at
  current data volume, but hardcoded-placeholder metrics (§2) mean this
  hasn't actually been load-tested against real aggregation queries yet.

---

## 14. V2 Migration Strategy

The codebase is **worth building on, not rewriting**. Core safety-critical
paths — offline GPS/SOS on mobile, SOS handling and role-gated status
transitions on the backend, live SOS/map/fishermen views on the dashboard —
are real, coherent, and already follow sound patterns (offline-first,
idempotent sync, service-layer separation in v2). The gap between V1 and the
V2 spec is not "the architecture is wrong," it's "several modules were
documented as complete before they were built" (AI, notifications, IoT,
trip UI, real weather) plus a handful of concrete, fixable defects (the
critical auth bug, the mobile build breakage, dead code, mocked analytics).

Recommended approach, reflected in `docs/ROADMAP.md`:
1. **Fix, don't replace**, the mobile build breakage and the critical auth
   vulnerability early — both are small, isolated patches with
   disproportionate impact.
2. **Extend the v2 `services/` pattern to v1** rather than introducing a
   third pattern — normalize, don't rearchitect.
3. **Wire up what already has a schema but no logic** before building new
   things — `RiskIncident`, `FamilyNotification`, and the notification
   dispatch layer are the highest-leverage "finish what's started" work.
4. **Build genuinely new modules (AI, IoT, notifications-as-real-dispatch,
   background scheduler) additively**, behind clear "SIMULATED" labeling
   until real integrations/hardware exist, per the governing brief's
   non-negotiable rules against faking capability.
5. **Consolidate documentation** into `docs/` (this file, plus
   `V2_ARCHITECTURE.md`, `ROADMAP.md`, and future per-module docs) and treat
   the ~30 root-level phase-summary files as historical/superseded rather
   than deleting them outright (they have some historical value but should
   no longer be treated as authoritative).

---

## Summary of critical items requiring near-term attention

| # | Issue | Severity |
|---|---|---|
| 1 | Anyone can self-register as `operator` via the API | Critical |
| 2 | Hardcoded operator credentials auto-seeded in production Docker image | Critical |
| 3 | Mobile app does not compile as committed (missing l10n codegen config) | High (blocks all mobile work) |
| 4 | Hardcoded weak DB/JWT secrets in committed `docker-compose.yml` | High |
| 5 | Notifications are fully stubbed — family/operators may believe alerts were sent when they weren't | High (safety-relevant) |
| 6 | No rate limiting on auth/SOS endpoints | Medium |
| 7 | Mobile session tokens stored in plaintext | Medium |
