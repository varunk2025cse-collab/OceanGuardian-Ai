# OceanGuardian AI — V2.0 Roadmap

High-level, 15 phases plus the audit phase. Each phase below states what V1
already provides (so we know what NOT to rebuild) and what's net-new. Do not
start a phase's detailed implementation plan until the previous phase is
built and verified — per the governing brief's process rules. This roadmap
will be revisited and each phase expanded into its own detailed plan
immediately before that phase begins.

See `docs/V1_AUDIT.md` for full findings and `docs/V2_ARCHITECTURE.md` for
the target system design and module-by-module gap analysis this roadmap is
based on.

> **Superseded by `docs/V2_CORE_IMPLEMENTATION_PLAN.md`'s 22-step order**
> for the actual execution sequence. As of 2026-07-25: Steps 0-8 (audit
> through live map) and Steps 9-21 (safety engine, weather, AI,
> SOS 2.0, incidents, dashboard/AI panel, family portal, notifications,
> security hardening) are complete and tested — see
> `docs/GOD_MODE_STATUS.md` for the authoritative, test-verified status of
> every module. Remaining: Step 22 items not yet done — CI pipeline, a
> scripted Demo Mode, and real-credential verification of the
> Anthropic/Twilio provider paths (both implemented, both unverified).

---

### Phase 0 — Audit *(complete)*
**Delivered:** `docs/V1_AUDIT.md`, `docs/V2_ARCHITECTURE.md`, this roadmap.
No application code changed.

### Phase 1 — Architecture Cleanup
**V1 has:** a working but inconsistent pattern — v2 routers delegate to a
services layer, v1 routers embed logic directly.
**Net-new work:** normalize v1 routers onto the v2 services pattern;
consolidate the role-check logic that v2 routers currently duplicate inline
back into `core/deps.py`; remove the dead code found in the audit (2 unused
mobile widgets, 5 orphaned dashboard pages). No behavior change — this is
pure refactoring, verified by the existing test suite continuing to pass.

### Phase 2 — Database Improvements
**V1 has:** a solid v1+v2 schema, but `RiskIncident`, `FamilyNotification`,
and `RiskModelMetric` are defined and unused; only 3 roles exist.
**Net-new work:** expand `UserRole` toward the 8-role target model; add
`roles`/`audit_logs` tables; wire up `RiskIncident` and
`FamilyNotification` so later phases have something real to write to. New
Alembic migration(s), no data loss, backward compatible with existing rows.

### Phase 3 — Offline-First Tracking Extension
**V1 has:** a genuinely solid offline-first GPS/SOS design on mobile, and a
complete trip lifecycle API on the backend that mobile never adopted.
**Net-new work:** build the mobile trip UI (start/pause/resume/complete)
against the *existing* backend `/trips/*` endpoints — this is the single
highest-leverage mobile gap identified in the audit. The underlying
offline-sync mechanics (SQLite outbox, `client_uuid` idempotency) are
reused unchanged, not redesigned.

### Phase 4 — SOS + Incident Management
**V1 has:** a real, role-gated SOS trigger/status API with offline-first
mobile support, but only a 4-state status model and an unused incident
timeline table.
**Net-new work:** expand the emergency-type taxonomy (man overboard, engine
failure, medical, fire, capsize risk, etc. per the governing brief); start
writing to `RiskIncident` on every SOS trigger so a real, immutable
timeline exists for later phases (dashboard incident view, AI incident
reports) to build on.

### Phase 5 — Rescue Command Center
**V1 has:** live SOS list/detail/map/fishermen views, all real. Analytics
page is mostly mocked (`ChartPlaceholder` components, hardcoded metrics).
**Net-new work:** replace the mocked Analytics page with real queries; add
a boat-list view (currently absent); remove the 5 dead orphan page files
(already scheduled in Phase 1, verify still gone).

### Phase 6 — Family Safety
**V1 has:** family link/unlink/status endpoints and a working mobile
`FamilyScreen`, but "notify family" never actually sends anything.
**Net-new work:** connect family alerts to the notification engine (built
in Phase 11); implement clear online/offline/last-known-location UI states
so families are never told a boat is "live" when the last update is stale
— a direct requirement from the governing brief's safety-first framing.

### Phase 7 — AI Safety Engine
**V1 has:** a real, functioning rule-based risk-scoring engine (8 weighted
factors) that is honest about being rule-based, not ML.
**Net-new work:** keep the scoring engine as the computational core; add an
explainability layer that turns the score into human-readable reasons and
a recommendation (e.g. "Risk Score: 78 HIGH — severe weather detected,
battery low..."). Decide during phase planning whether this text layer
needs an LLM call or can stay deterministic — either way, never claim
statistical validation or ML pedigree that doesn't exist.

### Phase 8 — AI Rescue Assistant
**V1 has:** nothing — no AI/LLM integration exists anywhere in the
codebase today.
**Net-new work:** a tool-calling assistant for rescue operators, backed
exclusively by validated tool functions that call the real `/api/v2/*`
service layer (never direct DB access). Must answer only from real system
data; no hallucinated operational facts.

### Phase 9 — IoT Device Abstraction
**V1 has:** nothing — no MQTT, no device gateway, no telemetry ingestion
protocol; boat health data is entirely manual entry today.
**Net-new work:** define the device-gateway interface and telemetry data
contract (device_id, boat_id, timestamp, GPS, battery, sensors...) so real
hardware can be added later without a backend rewrite. No real-hardware
claims — this phase is the interface only.

### Phase 10 — Hardware Simulator
**V1 has:** nothing.
**Net-new work:** `tools/device_simulator/` producing clearly-labeled
simulated telemetry against the Phase 9 interface, with scenario support
(normal trip, weather deterioration, engine failure, low battery,
communication loss, SOS) — this is what makes Phases 8-9's work testable
and demoable before real hardware exists.

### Phase 11 — Notification Engine
**V1 has:** a single `logger.warning()` call as the entire notification
system; `FamilyNotification` rows are never created by any code path.
**Net-new work:** real adapters (push at minimum, SMS/email as configured),
retryable and audited, with CRITICAL/HIGH/MEDIUM/LOW priority tiers. This
unblocks Phase 6 (family alerts) and closes one of the audit's flagged
safety-relevant gaps (notified-flags set without any message ever sent).

### Phase 12 — Analytics
**V1 has:** several genuinely computed metrics alongside some hardcoded
placeholder numbers presented as if computed (fixed risk-zone list,
`overdue_maintenance_boats=2` constant, fixed risk-tier percentages).
**Net-new work:** replace every remaining hardcoded placeholder with a real
aggregation query; add charts to the dashboard (currently `ChartPlaceholder`
stand-ins with no chart library).

### Phase 13 — Security Hardening
**V1 has:** several concrete, already-identified issues (see
`docs/V1_AUDIT.md` §10): the critical operator self-registration bug,
hardcoded secrets in `docker-compose.yml`, no rate limiting, wildcard CORS
default, plaintext mobile token storage, root-user Docker container.
**Net-new work:** fix each of the above. This phase closes findings, it
doesn't discover new ones — the audit already did that work.
*(Sequencing note: the self-registration bug is a live vulnerability today;
whether it gets hotfixed ahead of Phase 1 rather than waiting until here is
an open question for you to decide — see below.)*

### Phase 14 — Testing
**V1 has:** decent backend test coverage (13 files, ~4,174 lines) but
almost no mobile tests (1 smoke test) and zero dashboard tests; no CI
pipeline exists for any of the three codebases.
**Net-new work:** CI pipeline; mobile widget/unit tests (enabled by any
DI refactor from Phase 1 that makes the singleton services testable);
dashboard component tests; an end-to-end integration test covering
fisherman → GPS → offline storage → sync → backend → AI → alert → rescue
dashboard → family notification.

### Phase 15 — Deployment
**V1 has:** a working `docker-compose.yml` for local dev, but with secrets
committed in plaintext and no production-hardening.
**Net-new work:** externalize all secrets via `.env`/secret manager
(building on Phase 13's fixes), document local dev / mobile / IoT simulator
setup end-to-end, finalize a reproducible one-command demo mode per the
governing brief's Demo Mode module.

---

## Sequencing Note — Open Item

The critical operator self-registration vulnerability
(`docs/V1_AUDIT.md` §10, item 1) is formally scheduled under Phase 13, but
it's a live, trivially exploitable hole in the code today. Whether to patch
it immediately as a small out-of-sequence hotfix, or let it wait for Phase
13 in the normal order, depends on whether this codebase is deployed or
reachable anywhere right now. This is a direct decision for you, asked
separately from this roadmap.
