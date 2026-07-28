# OceanGuardian AI V2 — Core Implementation Plan (AI + GPS + Dashboard)

**Scope of this document:** the "core" build — GPS tracking, offline-first
sync, trip lifecycle, weather intelligence, AI safety engine, SOS, incident
management, rescue dashboard, family portal, notifications, security,
testing, and demo simulation. Explicitly **excludes** IoT/hardware, which is
deferred to a later phase per the governing brief.

This document supersedes the pacing details of `docs/ROADMAP.md`'s Phases
3-12 with the more specific 22-step order below, while keeping that
roadmap's phases 0-2 (audit, architecture cleanup, database improvements)
and 13-15 (security/testing/deployment) as the surrounding context. Nothing
here contradicts `docs/V1_AUDIT.md` or `docs/V2_ARCHITECTURE.md` — treat
this as the detailed execution plan for the modules those documents already
scoped.

---

## 1. What already works / partial / mocked / missing

(Full detail in `docs/V1_AUDIT.md` §2; summarized here against the 22 steps.)

| Step | Area | Status |
|---|---|---|
| 3 | GPS tracking (mobile) | **Works** — `LocationService` captures lat/lon/accuracy/speed/heading via `geolocator` on a 5-min timer; missing altitude/battery/network/tracking-status fields |
| 4 | Offline storage | **Works** — SQLite outbox (`pending_locations`, `pending_sos`), source of truth before any network call; missing explicit `sync_status` enum (currently a bare boolean) |
| 5 | Sync engine | **Works, not hardened** — connectivity-triggered + 30s-polled sync, SOS-first priority, per-item error isolation; missing exponential backoff, guaranteed ordering, and a UI-facing status stream |
| 6 | Trip lifecycle | **Backend-only** — full CRUD API exists (`/api/v1/trips/*`), zero mobile UI/model. Biggest gap in the whole codebase. |
| 7 | Backend tracking APIs | **Partial** — `/api/v1/locations/*` works for ingestion/history; no fleet-level or freshness-aware endpoint for the dashboard exists |
| 8 | Live map | **Partial** — dashboard has a real Leaflet map with SOS + weather markers; no vessel/fleet markers. Mobile has a raw point-trail map, no trip route or freshness display. Family screen shows raw lat/lon, no freshness state. |
| 9 | Safety status | **Missing** — no SAFE/MONITOR/CAUTION/HIGH_RISK/CRITICAL/OFFLINE/UNKNOWN state exists anywhere |
| 10 | Weather intelligence | **Fake** — `WEATHER_PROVIDER` config exists, never read; data is seed-only |
| 11 | Risk engine | **Rule-based, real computation, mislabeled provenance** — `RiskPredictionService` is a genuine weighted scorer but hardcodes `model_version`/`confidence` as literals |
| 12 | AI safety intelligence / explainability | **Missing** — no reasoning/recommendation text generation layer exists |
| 13 | AI early warning | **Missing** |
| 14 | SOS | **Works** — offline-first trigger + retry on mobile, role-gated status transitions on backend; emergency-type taxonomy is a single loosely-typed field, not the spec's 11 types |
| 15 | Incident engine | **Schema-only** — `RiskIncident` table exists, nothing reads/writes it; SOS status is a simplified 4-state model, not the spec's 8-state incident lifecycle |
| 16 | Rescue dashboard | **Mostly real** — live SOS/map/fishermen views; Analytics page is mostly mocked (`ChartPlaceholder`, hardcoded trends) |
| 17 | Rescue dashboard AI | **Missing** entirely |
| 18 | AI tool system | **Missing** — no LLM integration anywhere in the codebase; `copilot_sessions`/`copilot_conversations` tables exist unused |
| 19 | Family portal | **Partial** — link/status/focus-map exist; safety-status field doesn't exist yet (depends on Step 9) |
| 20 | Notification engine | **Fully stubbed** — the entire system is one `logger.warning()` call; `FamilyNotification` rows are never created |
| 21 | Security | **One critical bug already fixed** (operator self-registration) — remaining: hardcoded `docker-compose.yml` secrets, no rate limiting, wildcard CORS, plaintext mobile token storage |
| — | Mobile build | **Broken as committed** — missing l10n codegen config (`generate: true` + `l10n.yaml`); confirmed still broken this session, `flutter` toolchain is available in this environment to actually fix and verify it |

---

## 2. What's reused vs. refactored vs. net-new

**Reused unchanged** (audited as genuinely solid — do not rewrite):
- Mobile offline-first design: SQLite-first writes, `client_uuid` idempotency, cache-first reads for reference data
- Backend `client_uuid` dedup pattern for locations and SOS
- v2 services-layer pattern (`app/services/*.py`) as the template for all new backend logic
- Backend JWT auth, RBAC dependency structure (`core/deps.py`)
- Rescue dashboard's existing live SOS/map/fishermen wiring

**Refactored:**
- `backend/app/routers/trips.py` logic moves into a new `trip_service.py` (matches the v2 pattern; Phase 1's already-planned v1→services normalization starts here rather than as a separate no-op pass)
- Mobile `SyncService` gains backoff/ordering/status-stream without changing its core connectivity-triggered design

**Net-new:**
- Trip lifecycle mobile UI (models, service, screens)
- Location freshness computation (server-side, single source of truth)
- `/api/v2/tracking/*` fleet + history endpoints
- Explicit `sync_status` state machine (mobile outbox)
- Everything in Steps 9-22 (weather, risk explainability, AI, SOS taxonomy expansion, incidents, dashboard AI, notifications) — scoped in later passes per sections 4-5 below

---

## 3. Implementation Order (the 22 steps, as scoped for the core build)

This pass (approved, in progress) covers **Steps 1-8**:

1. Repository audit — done (`docs/V1_AUDIT.md`)
2. Architecture plan — done (`docs/V2_ARCHITECTURE.md`, this document)
3. GPS tracking — extend existing `LocationService` with altitude/battery/network/tracking-status
4. Offline storage — explicit `sync_status` enum on the mobile outbox
5. Sync engine — exponential backoff, ordering, status stream
6. Trip lifecycle — mobile UI against the existing backend API + a proper state machine
7. Backend tracking APIs — `/api/v2/tracking/fleet` and `/history`, freshness computation
8. Live map — fleet markers (dashboard), trip route + freshness (mobile), freshness label (family)

**Deferred to the next pass** (Steps 9-22), pending your review of this
slice and decisions on weather provider / LLM integration / notification
channels:

9. Safety state (SAFE/MONITOR/CAUTION/HIGH_RISK/CRITICAL/OFFLINE/UNKNOWN)
10. Weather integration (real provider — Open-Meteo Marine API is the
    natural default since it's already named in backend config and needs
    no API key, but confirm before wiring it in)
11. Risk engine (extend the existing rule-based scorer; fix the
    hardcoded `model_version`/`confidence` literals to reflect what's
    actually true)
12. AI safety intelligence / explainability layer — **needs your input**:
    wire a real LLM (e.g. Claude via the Anthropic API, requires an API
    key from you) for natural-language reasoning/recommendation text, or
    keep it fully deterministic/template-based for now with a swappable
    interface for a real LLM later
13. AI early warning
14. SOS — expand emergency-type taxonomy to the spec's 11 types
15. Incident engine — wire up the unused `RiskIncident` table, implement
    the 8-state lifecycle with a transition audit trail
16. Rescue dashboard — replace mocked Analytics, add incident timeline UI
17. Rescue dashboard AI panel — depends on 12 and 18
18. AI tool system — controlled tool functions (`get_boat_status`,
    `calculate_safety_risk`, etc.) that the AI in 12/17 calls; never
    direct DB access from AI
19. Family portal — surface safety status (from 9) and rescue status (from 15)
20. Notifications — **needs your input**: real push (Firebase Cloud
    Messaging) / SMS (e.g. Twilio) / email (SMTP) all require provider
    credentials you'd need to supply; without them this phase delivers a
    real in-app notification channel + audit/retry infrastructure with a
    pluggable-but-clearly-unconfigured external-channel interface, per the
    "never fake capability" rule
21. Security hardening — remaining items from `docs/V1_AUDIT.md` §10
22. Testing, demo simulation, documentation, production-readiness review

---

## 4. Database Changes (this pass)

New Alembic migration, additive/nullable only, no data loss:
- `location_pings`: `altitude_meters FLOAT NULL`, `battery_percent FLOAT NULL`, `network_type VARCHAR(20) NULL`, `source VARCHAR(20) NOT NULL DEFAULT 'MOBILE_GPS'`
- `trips.status`: values constrained (at the application layer, via `trip_service.py`) to `PLANNED|ACTIVE|RETURNING|COMPLETED|CANCELLED|EMERGENCY` — no column type change needed, it's already a string

No new tables in this pass — `RiskIncident`/`FamilyNotification` wiring is Steps 15/20.

## 5. API Changes (this pass)

Additive only, `/api/v1` untouched:
- `GET /api/v2/tracking/fleet` (operator) — latest position + freshness per active-trip fisherman
- `GET /api/v2/tracking/{fisherman_id}/history` (family-if-linked / operator / self)

## 6. Mobile Changes (this pass)

- `mobile/l10n.yaml` (new), `pubspec.yaml` (`generate: true`) — fixes the build
- `lib/models/trip.dart`, `lib/services/trip_service.dart` (new)
- Trip start/active/end UI wired into `home_shell.dart`
- `location_service.dart`, `local_db_service.dart` — new fields + `sync_status`
- `sync_service.dart` — backoff + ordering + status stream
- `location_screen.dart`, `family_screen.dart` — freshness display

## 7. Dashboard Changes (this pass)

- `MapPagePremium.jsx` — fleet vessel markers from the new tracking endpoint
- `api/admin.js` (or a new `api/tracking.js`) — thin wrapper for the new endpoint

## 8. AI Architecture (for Steps 12/17/18 — documented now, built later)

Per the governing brief's non-negotiable rules: AI is decision support, not
authority. Architecture (to be built in the next pass):

```
Rescue Dashboard AI Panel / Mobile Explainability Text
                    |
             AI Controller
                    |
     Authorized AI Tools (get_boat_status, calculate_safety_risk,
     get_active_incidents, get_latest_location, get_weather, ...)
                    |
        Existing services/ layer (harbor, tracking, risk_prediction,
        checkin, escalation, family_portal, analytics)
                    |
                Repositories / DB
```

The rule-based risk engine (already real) stays the computational core.
An LLM, if you choose to wire one in, sits **above** it purely to translate
the already-computed score/factors into natural language — it never
computes the score itself, and the system must keep working with template-
based text if the LLM call fails or isn't configured. This satisfies "the
system must remain functional if an external AI provider is unavailable"
and "never rely entirely on an LLM for safety-critical decisions."

## 9. Testing Strategy (this pass)

- Backend: pytest, extending the existing 185-test suite. New coverage for
  trip state-machine transitions, tracking-endpoint authorization
  (family/operator/self boundaries), freshness computation, and the new
  location fields/migration.
- Mobile: `flutter analyze` (currently cannot even run due to the build
  bug — fixing that is a prerequisite deliverable in itself), plus targeted
  unit tests for `TripService` and the sync-status stream.
- Dashboard: `npm run build` as a smoke check (no test framework exists yet
  — adding one is Step 22/Phase 14 territory, out of scope here).

Full step-by-step detail for Steps 3-8 is in the approved implementation
plan for this pass; this document will be extended with the same structure
for Steps 9-22 as each subsequent pass is planned and approved.
