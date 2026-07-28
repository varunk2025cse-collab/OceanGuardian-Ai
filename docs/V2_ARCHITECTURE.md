# OceanGuardian AI — V2.0 Target Architecture

This document describes where V2.0 is headed and exactly what's missing to
get there, based on the ground truth established in `docs/V1_AUDIT.md`.
It is deliberately additive: V2 is built **on top of** the existing FastAPI
backend, Flutter app, and React dashboard, not a replacement for them.

---

## 1. System Diagram

```
                              OCEANGUARDIAN AI
                                     |
        --------------------------------------------------------------
        |                  |                  |                     |
  Fisherman App      Family Portal      Rescue Center          Authority
  (Flutter, keep)   (same Flutter app,  (React dashboard,      Portal (new
                     role-switched tab)  keep, extend)          roles, extend
                                                                 dashboard RBAC)
        --------------------------------------------------------------
                                     |
                          API Gateway (existing FastAPI app)
                          /api/v1 kept as-is, /api/v2 extended
                                     |
        --------------------------------------------------------------
        |              |                |                |          |
   Core APIs      AI Engine (new)   IoT Gateway (new)  Notification  Background
   (v1+v2         calls real tool    device interface   Engine (new, Jobs (new —
   routers,        functions only,   + simulator, no    replaces the nothing runs
   existing)        no direct DB     real hardware       log-line     on a timer
                     access)          claims              stub)        today)
        --------------------------------------------------------------
                                     |
                          PostgreSQL (existing schema,
                          extended: roles, audit_logs,
                          RiskIncident + FamilyNotification
                          actually wired up)
                                     |
                          Analytics / Events (real queries,
                          replacing hardcoded placeholder
                          metrics found in the audit)
                                     |
                          External Services (real weather API,
                          push/SMS/email provider, future
                          IoT/satellite adapters — behind
                          interfaces, added incrementally)
```

---

## 2. Layering Principles (carried forward from the audit's strengths)

- **Presentation** (Flutter screens, React pages) stays thin — no business
  logic in widgets/components. This is already true for most of the mobile
  app and dashboard; V2 work should not regress it.
- **API routers** stay thin and delegate to a **services layer** — this is
  already the pattern in `backend/app/routers/v2/*.py` and
  `backend/app/services/*.py`. Phase 1 normalizes v1 routers to match it
  instead of introducing a third pattern.
- **AI never touches the database directly.** Every AI-facing capability
  (Safety Engine reasoning, Rescue Assistant, MCP tools) calls the same
  validated service-layer functions everything else uses. This is a hard
  requirement carried from the governing brief, not just a preference.
- **IoT ingestion is an adapter, not a special path.** Device telemetry
  lands through the same validation/persistence layer as manually-entered
  boat health data; the only thing that changes is who submits it.
- **Notifications are dispatched through adapters** (push, SMS, email —
  each swappable) behind one `NotificationEngine` interface, so a missing
  provider credential degrades a specific channel, not the whole system.
- **Everything simulated is labeled simulated.** The IoT simulator, any
  crew wearable data, and any AI-generated recommendation text must be
  visually and structurally distinguishable from real sensor/operator data,
  per the governing brief's non-negotiable rules.

---

## 3. What Already Exists vs. What's Net-New

### Already real, keep as-is (do not rewrite)
- Offline-first GPS capture + sync on mobile (SQLite outbox, idempotent
  batch sync)
- Offline-first SOS trigger + retry on mobile
- SOS trigger/status-transition API + role gating on the backend
- Rescue dashboard live SOS list/detail/map/fishermen views
- v2 service-layer pattern (harbor, boat_health, checkin, escalation,
  risk_prediction, family_portal, analytics)
- Rule-based risk scoring engine (`risk_prediction.py`) — keep the
  computation, add explainability on top, never relabel it as ML

### Needs to be finished, not rebuilt (schema exists, logic doesn't)
- `RiskIncident` table → wire up as the immutable incident timeline
- `FamilyNotification` table → wire up as an actual notification queue
- `WEATHER_PROVIDER` config → actually call the configured provider

### Needs to be fixed (defects found in the audit)
- Operator self-registration vulnerability
- Mobile build breakage (l10n codegen)
- Mocked dashboard Analytics page
- Hardcoded secrets in `docker-compose.yml`
- Dead/orphaned code (5 dashboard pages, 2 mobile widgets)

### Genuinely net-new (nothing exists today)
- AI Safety Engine explainability layer, AI Rescue Assistant, MCP tool
  exposure, AI-generated incident reports
- IoT device gateway + hardware simulator
- Real notification dispatch adapters
- Background job scheduler
- 5 additional user roles + expanded RBAC
- Trip lifecycle UI in the mobile app (backend API already exists)
- CI pipeline across all three codebases
- Crew safety features (roster, check-in/out, wearable simulation)

---

## 4. Gap Analysis: V1 → V2 Spec, by Module

| V2 Module | V1 status | Gap to close |
|---|---|---|
| Fisherman App core | Mostly real | Fix build (l10n), add trip UI against existing backend API, move tokens to secure storage |
| Offline-first sync | Real, solid | Extend the existing pattern to trip data; no redesign needed |
| Live boat tracking | Partial | Location ping/history exists; add "last known vs. live" staleness UI, geofencing |
| Family safety | Partial | Status/link endpoints exist; connect to a real notification dispatch |
| Smart SOS | Mostly real | Expand emergency-type taxonomy; keep the offline-first trigger flow unchanged |
| AI Safety Engine | Rule-based only | Keep the rule engine; add explainable reasoning/recommendation text; never claim unvalidated ML |
| Weather Intelligence | Static/seed-only | Real provider integration (Open-Meteo, already named in config) behind a scheduled job |
| IoT/Hardware layer | None | New: device gateway interface + simulator, additive, no real-hardware claims |
| Communication (multi-path) | None | New: adapter interfaces only; no fake LoRa/satellite capability claims |
| Boat health | Manual entry only | Keep manual entry as the real data source, clearly labeled; predictive maintenance later |
| Crew safety | None | New, simulation-only until wearable hardware exists |
| Rescue command center | Mostly real | Replace mocked Analytics page with real queries; extend incident lifecycle; remove dead pages |
| AI Rescue Assistant / MCP / AI Agent | None | New — real tool functions against real data only, never hallucinate |
| AI Incident Report | None (schema unused) | New — built on top of the now-wired-up `RiskIncident` table |
| Fisheries intelligence | Real but static | Keep; add source/timestamp labeling since data is manually seeded |
| Analytics | Partly fake | Replace hardcoded placeholder numbers with real aggregation queries |
| Notification engine | Stub only | New — real adapters, priority tiers, retry + audit |
| Multilingual | Partial, broken build | Fix l10n build; audit hardcoded English strings found in the mobile audit |
| Security | Multiple issues | Fix operator self-registration (critical), secrets, rate limiting, CORS, mobile token storage |
| Database | Solid schema, some unused tables | Wire up `RiskIncident`/`FamilyNotification`; add `roles`/`audit_logs` |
| API design | Reasonably consistent | Extend `/api/v2`; do not break `/api/v1` |
| Testing | Backend decent, mobile/dashboard ~0 | Add mobile widget tests, dashboard tests, CI pipeline |
| Deployment | Basic compose works | Harden Dockerfile (non-root, healthcheck), externalize secrets |

---

## 5. Role Model Target

Current: `fisherman`, `family`, `operator` (3).
Target: add `boat_owner`, `harbor_officer`, `fisheries_officer`, `ngo`,
`system_admin` (8 total), each with RBAC enforced consistently through
`core/deps.py` (not duplicated inline as v2 routers currently do). This is
Phase 2/13 work — see `docs/ROADMAP.md`.

---

## 6. Non-Negotiable Constraints Carried Into Every Phase

These come directly from the governing brief and apply to all V2 work:

- Never fake hardware, GPS, satellite, or LoRa capability.
- Never present rule-based scoring as machine learning, or hardcoded
  placeholder numbers as computed analytics.
- AI never overrides emergency professionals; manual SOS must work even if
  every AI/API dependency fails.
- Location data access is least-privilege; family members only see boats/
  trips they're authorized to follow.
- No secrets committed to the repository; the audit found several that
  need remediation (Phase 13, or sooner — see open question in the
  approved plan).
