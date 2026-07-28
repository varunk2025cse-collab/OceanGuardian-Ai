# Incident Engine

`backend/app/services/incident_service.py` — V2 core build Phase 15.

## What changed from V1

`risk_incidents` existed in the V1 schema but nothing ever read or wrote
it (`docs/V1_AUDIT.md` §2/§11 — "schema-only, unused"). It is not a new
table — it's a table that finally has an owner. Extended with `status`,
`fisherman_id`, `acknowledged_by/at`, `closed_at` (migration
`008_safety_incident_engine`), plus a new child table `incident_events`
for the transition audit trail.

## State machine (8 states)

`RECEIVED → ACKNOWLEDGED → ASSESSING → RESCUE_DISPATCHED →
RESCUE_IN_PROGRESS → SAFE → CLOSED`, plus `CANCELLED` (reachable from
every non-terminal state). Illegal transitions raise 409, unknown status
values raise 422 — no arbitrary transitions, matching the trip/incident
state-machine pattern already established for trips
(`app/services/trip_service.py`).

Every transition writes an `IncidentEvent` row: actor, timestamp,
previous status, new status, reason. Rows are never updated or deleted —
this is the audit trail.

## Auto-creation

Every SOS trigger auto-creates a `RECEIVED` incident
(`IncidentService.create_from_sos`) — see `docs/SOS_ARCHITECTURE.md`. The
first `IncidentEvent` (actor=None, "system") records this.

## Authorization

Operator sees everything. A fisherman sees their own incidents. A family
member sees incidents for a fisherman they're explicitly linked to (same
`FamilyLink` check used throughout — tracking, safety, family status).

## Incident Report Generator

`IncidentService.generate_report()` — pulls only real, already-recorded
fields (fisherman, trip, SOS alert, full timeline, response time computed
from `created_at`/`acknowledged_at`). Missing fields are `null`, never
guessed. `generate_incident_summary` (AI tool) wraps this with a
narrated summary via `docs/AI_ARCHITECTURE.md`'s provider.

## API

`GET /api/v2/incidents/active`, `GET /{id}`, `GET /{id}/timeline`,
`POST /{id}/transition`, `GET /{id}/report`.

Dashboard: `rescue-dashboard/src/pages/IncidentsPage.jsx` — list, timeline,
transition buttons scoped to legal next-states only.

## Status: IMPLEMENTED

9 tests in `tests/test_god_mode_safety_incident_ai.py` cover the full
lifecycle (received → acknowledged → dispatched → in-progress → safe →
closed), illegal-transition rejection, authorization boundaries, and
report field accuracy (including that unacknowledged incidents correctly
report `response_time_seconds: null`, not a fabricated value).
