# OceanGuardian AI — Product Bible

**This is the source of truth for what OceanGuardian AI is, who it serves,
what exists today, and what a complete government-grade marine safety
platform still needs.** Every entry below is grounded in the actual
codebase (verified against `backend/app/`, `mobile/lib/`,
`rescue-dashboard/src/`) — not aspirational. Status tags used throughout:

- **LIVE** — implemented, tested, working today
- **PARTIAL** — implemented but incomplete or unverified
- **MISSING — BUILDABLE NOW** — no infrastructure blocker, can be built
  with the tools and access available in this environment
- **MISSING — INFRASTRUCTURE-GATED** — requires something this
  environment doesn't have: paid API credentials (speech/translation),
  hardware (IoT sensors), data-sharing agreements (satellite/AIS feeds,
  government scheme databases), or a mobile device/app-store presence

---

## 1. Vision

A marine safety and fisheries intelligence platform that a fisherman with
limited digital literacy can operate under stress, at sea, with no
signal — and that gives rescue authorities and families the same honest,
real-time picture at the moment it matters most.

## 2. Mission

Reduce the time between "something is wrong" and "help is coming," and
close the information gap between a fisherman at sea, their family on
shore, and the authorities who can help — without ever pretending to know
more than the data actually shows.

## 3. Objectives (measurable, not aspirational)

1. Manual SOS always works, even with every other system down.
2. A family member always knows their fisherman's last known state —
   honestly labeled (LIVE vs STALE vs UNKNOWN), never falsely reassuring.
3. A rescue operator can go from "alert received" to "resources
   dispatched" using only real data, with a full audit trail.
4. Every AI-generated statement is explainable and traceable to real
   underlying data — never a hallucinated fact presented as certain.
5. The system degrades safely: losing any one integration (weather, AI,
   notifications) must never disable another.

## 4. User Personas

| Persona | Core need | Digital literacy | Connectivity |
|---|---|---|---|
| **Fisherman** | One-touch SOS, simple trip tracking, weather in plain language | Low-to-medium; Tamil-first | Frequently offline at sea |
| **Family member** | "Is my fisherman okay, right now?" without jargon | Low-to-medium | Usually connected (on shore) |
| **Rescue operator** | Fast, accurate situational awareness; no false alarms | Medium-to-high; trained | Reliable (control room) |
| **Fisheries/harbor officer** *(role not yet built)* | Fleet-wide oversight, scheme administration | Medium-to-high | Reliable |
| **NGO/relief organization** *(role not yet built)* | Coordination during widescale events (cyclones) | Medium-to-high | Variable |
| **System administrator** *(role not yet built)* | User/role management, audit oversight | High | Reliable |

## 5. Stakeholders

Fishermen and their families (primary beneficiaries), state Fisheries
Departments, Coast Guard / marine rescue authorities, harbor
administrations, NGOs running relief operations, and — as a long-term
partner, not a current integration — meteorological agencies (INCOIS/IMD)
for authoritative marine warnings.

## 6. Problem Statements

1. A fisherman in distress at sea often has no reliable way to alert
   anyone, and even when they do, the alert can arrive without enough
   context for a fast, correct rescue response.
2. Families have no visibility into a fisherman's status once they're out
   of phone range, leading to prolonged uncertainty during genuine
   emergencies and unnecessary anxiety during normal trips.
3. Rescue operators often work from incomplete, unverified, or stale
   information, slowing triage and resource allocation.
4. Fishermen lack easy access to weather, market, and government scheme
   information in their own language, at the moment they need it.
5. There is no unified system connecting these three groups — each
   currently relies on ad hoc phone calls, VHF radio, or nothing at all.

## 7. Functional Requirements

See §9 (module breakdown) for the full, current, per-module functional
requirement status. Top-level requirement categories: identity &
authentication, boat/trip management, offline-first location tracking,
emergency SOS, incident lifecycle management, family visibility, weather
intelligence, AI-assisted safety scoring and explanation, rescue
operations dashboard, fisheries market/scheme information, notifications,
analytics, and (future) IoT hardware integration.

## 8. Non-Functional Requirements

| Category | Requirement | Status |
|---|---|---|
| **Offline-first** | Core safety functions (GPS capture, SOS trigger) work with zero connectivity | LIVE |
| **Security** | RBAC, no public privilege escalation, no committed secrets, rate limiting on auth | LIVE |
| **Explainability** | Every AI safety statement traceable to real computed data | LIVE |
| **Honesty** | No fabricated data ever presented as real/live/safe | LIVE (actively audited — see `docs/GOD_MODE_STATUS.md` §7) |
| **Multilingual** | Tamil + English throughout | PARTIAL — mobile app fully localized; dashboard is English-only |
| **Accessibility** | WCAG-aligned contrast, large touch targets, screen-reader support | PARTIAL — large touch targets and high contrast present in mobile theme; no formal accessibility audit or screen-reader testing performed |
| **Performance at scale** | Fleet-wide operations perform well with hundreds of concurrent vessels | PARTIAL — documented as unbatched, known limitation |
| **Disaster recovery** | Database backup/restore strategy, documented RTO/RPO | MISSING — BUILDABLE NOW |
| **Observability** | Structured logging, health checks | PARTIAL — `/health`, `/api/v1/system-info` exist; no centralized log aggregation or alerting |
| **CI/CD** | Automated testing and deployment gate | LIVE (CI) / MISSING (CD — no automated deployment pipeline) |

## 9. Architecture

See `docs/V2_ARCHITECTURE.md` for the full diagram. Summary: Flutter
mobile app (offline-first SQLite outbox) → FastAPI backend (PostgreSQL,
service-layer architecture) → React rescue dashboard. AI is a thin
explanation/tool-calling layer over deterministic services, never the
source of truth for safety data.

## 10. Database

24 tables currently live across `backend/app/models/` (users, boats,
trips, location_pings, sos_alerts, family_links, weather_alerts,
market_prices, govt_schemes, harbors + the Phase 5 intelligence layer:
risk_incidents, incident_events, safety_escalations, check_in schedules,
boat_health/fuel/maintenance, family_portal_access/notifications,
analytics_* tables, and the still-unused copilot_sessions/conversations
pair — see §11 Gap Analysis). Full schema: `docs/DATABASE.md` *(does not
yet exist — see gap list)*.

## 11. Microservices / Service Layer

Not a microservices architecture — a monolithic FastAPI app with a clean
internal service-layer boundary (`backend/app/services/*.py`), which is
the right architecture at current scale. Splitting into real
microservices before there's a scaling reason to would be premature
complexity, not a missing feature.

## 12. AI Services — current inventory

| AI capability | Status |
|---|---|
| Deterministic Safety State Engine (rule-based scoring) | LIVE |
| AI explainability layer (template provider) | LIVE |
| AI explainability layer (real Anthropic/Claude) | PARTIAL — implemented, unverified (no API key in this environment) |
| Rescue AI panel (fixed-intent, tool-calling) | LIVE |
| Controlled AI tool layer (16 tools) | LIVE |
| Early warning (multi-factor combination detection) | LIVE (snapshot-based, not trend-based — documented limitation) |
| Voice assistant / speech recognition / speech synthesis | MISSING — INFRASTRUCTURE-GATED (needs a speech API: Google Cloud Speech, Azure Speech, or on-device model — none configured, no credentials) |
| Real-time translation service | MISSING — INFRASTRUCTURE-GATED (mobile app has static bilingual UI strings; a dynamic translation service for arbitrary text — e.g. translating a government document — needs a translation API) |
| Fishing recommendation AI | MISSING — INFRASTRUCTURE-GATED (needs historical catch data this platform doesn't collect, and fishing-zone data from a government/research partner) |
| Predictive maintenance AI | MISSING — BUILDABLE NOW, with a caveat: real predictive maintenance needs historical failure data to train on, which doesn't exist yet. A rule-based "maintenance due soon" heuristic (mirroring the Safety Engine's honest rule-based approach) is buildable immediately; a real ML model is not, for the same reason `docs/V1_AUDIT.md` flagged the old risk-prediction "model" as not actually ML |
| Navigation AI (bearing/distance/ETA to nearest safe harbor) | LIVE — see `docs/NAVIGATION_AI.md`. Straight-line compass guidance only; full route optimization around weather/currents/obstacles remains INFRASTRUCTURE-GATED (needs bathymetry/AIS/current data) |
| Image/video/satellite intelligence | MISSING — INFRASTRUCTURE-GATED, explicitly out of scope per this project's own non-negotiable rules against faking hardware/satellite capability |
| AI memory / conversation history / learning engine | MISSING — BUILDABLE NOW for conversation history (store AI panel query/response pairs); "learning" in the sense of a model that improves from usage is INFRASTRUCTURE-GATED (needs an ML training pipeline and real usage data at volume) |

## 13. UI Design System

Mobile: `mobile/lib/theme/app_theme.dart` — `AppColors`/`AppTheme`, WCAG
AAA-oriented contrast, 60dp minimum touch targets, large fonts for Tamil
readability. Dashboard: `rescue-dashboard/src/theme/colors.js` + shared
`Card`/`Button`/`Badge` components (a real, followed design system —
verified and enforced during this session's design-consistency audit).
**Gap:** no written design-system documentation page for either app.

## 14. Security

See `docs/SECURITY.md` for the full, current, audited posture. Summary:
JWT auth, bcrypt, RBAC (3 roles — see §16 gap), rate limiting on
auth endpoints (never on SOS), no committed secrets, location access is
authorization-checked everywhere. Known gaps: single-process rate
limiter, no dependency vulnerability scanning, `python-jose` dependency
risk.

## 15. Deployment, Monitoring, Disaster Recovery

Deployment: `docs/DEPLOYMENT.md` (Docker Compose, manual). Monitoring:
`/health` and `/api/v1/system-info` only — no metrics dashboard, no
alerting, no log aggregation. **Disaster recovery: MISSING — BUILDABLE
NOW** (no documented backup/restore procedure, no defined RTO/RPO).

## 16. Testing Strategy

`docs/TESTING.md`. 236 backend tests, 10 mobile tests, dashboard has no
test framework (documented gap). No accessibility or performance test
suite exists — **MISSING — BUILDABLE NOW** for basic versions of both
(e.g. axe-core-style automated accessibility checks for the dashboard;
k6/locust load tests for the backend).

---

## Gap Analysis — Government-Grade Platform Checklist

| Area | Gap | Category |
|---|---|---|
| Roles | Only 3 of 8 target roles exist (fisherman/family/operator; missing boat owner, harbor officer, fisheries officer, NGO, sysadmin) | BUILDABLE NOW |
| Voice assistant | Not built | INFRASTRUCTURE-GATED |
| Speech recognition/synthesis | Not built | INFRASTRUCTURE-GATED |
| Real-time translation service | Not built (static bilingual UI only) | INFRASTRUCTURE-GATED |
| IoT device gateway | Interface point exists (`LocationPing.source`), no real ingestion | INFRASTRUCTURE-GATED (no hardware) |
| Satellite/video/image intelligence | Not built | INFRASTRUCTURE-GATED, explicitly out of scope |
| Real SMS/push notifications | Implemented, unverified (no Twilio/FCM credentials) | INFRASTRUCTURE-GATED |
| Real LLM (Claude) AI explanations | Implemented, unverified (no API key) | INFRASTRUCTURE-GATED |
| Disaster recovery plan | Not documented | BUILDABLE NOW |
| Accessibility audit | Not performed | BUILDABLE NOW (automated pass) |
| Dashboard test suite | Doesn't exist | BUILDABLE NOW |
| CI/CD deployment pipeline | CI exists, CD doesn't | BUILDABLE NOW |
| Database schema documentation | Doesn't exist | BUILDABLE NOW |
| Demo Mode script | Exists, verified working | LIVE |
| Navigation AI (bearing/distance/ETA to nearest safe harbor) | Built, tested (`docs/NAVIGATION_AI.md`) | LIVE |
| Crew-level safety (roster, wearables) | Not built | INFRASTRUCTURE-GATED (no wearable hardware) |
| Fishing-zone/catch recommendation AI | Not built | INFRASTRUCTURE-GATED (no data source) |
| Government scheme data | Static seed data only | INFRASTRUCTURE-GATED (needs a live government data feed/partnership) |

---

## How to use this document

This is the audit — not a promise that everything marked
INFRASTRUCTURE-GATED will remain unbuilt forever. It means: building it
*honestly* (not faked) requires something (credentials, hardware, a data
partnership) that isn't available in this development environment right
now. The BUILDABLE NOW items are real, scoped, and can be built next.
See the conversation for a proposed prioritized build order.
