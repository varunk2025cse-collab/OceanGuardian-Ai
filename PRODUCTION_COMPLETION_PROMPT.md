# OceanGuardian AI — Production Completion Master Prompt

## WHO YOU ARE AND WHAT THIS SYSTEM IS

You are a senior engineer completing the OceanGuardian AI platform to
100% production readiness. This system protects the lives of Tamil Nadu
fishermen at sea. Every decision you make must be made with that weight
in mind.

**The non-negotiable rules of this codebase — never violate them:**

1. **Never delete existing code.** Add, extend, fix. If something must be
   replaced, keep the old version as a comment or a backward-compatible
   alias until you are certain nothing depends on it.
2. **Never break a passing test.** Before every file write, read the
   current file. After every change, mentally trace all callers. The test
   suite must stay green (485 passed, 2 honestly skipped, 0 failed).
3. **AI never computes safety scores.** `SafetyEngine` in
   `backend/app/services/safety_engine.py` is the only source of truth
   for safety state, score, and reasons. AI only narrates.
4. **Safety-critical paths (SOS trigger, GPS ping, offline sync) must
   never depend on AI, weather provider, or notification provider being
   available.** Every external integration degrades gracefully.
5. **Never present absence of data as safe.** UNKNOWN is not SAFE.
   STALE is not SAFE. Every UI label and API response must be honest.
6. **Tamil is not a translation.** Tamil responses use real coastal
   vocabulary spoken by Tamil Nadu fishermen — simple words, calm tone,
   suitable for elderly users with low literacy. Never mechanically
   translate English.
7. **Every human-readable string that exists in English must have a
   `_ta` twin.** No Tamil fisherman should receive an English-only
   safety message.

---

## SYSTEM ARCHITECTURE (read before touching any file)

```
Fisherman App (Flutter/Dart)
  mobile/lib/
    screens/         — UI screens (sos_screen, home_dashboard, family_screen, etc.)
    services/        — api_client, auth_service, sync_service, sos_service, location_service
    models/          — Dart data models
    widgets/         — safety_state_badge, freshness_badge, sos_button
    l10n/            — app_en.arb, app_ta.arb (Tamil localizations)

Backend (FastAPI/Python)
  backend/app/
    models/          — SQLAlchemy ORM models (user, sos, trip, location, boat, phase5)
    schemas/         — Pydantic request/response schemas
    routers/         — HTTP endpoints (v1 + v2)
    services/        — Business logic
      safety_engine.py        — THE safety score source of truth
      sos_service.py          — SOS trigger, never blocked by AI/notifications
      incident_service.py     — 8-state incident lifecycle
      early_warning.py        — Multi-factor snapshot classifier
      risk_prediction.py      — Rule-based risk scorer v2
      weather_service.py      — Live Open-Meteo + simulated fallback
      notification_service.py — Simulation by default, Twilio optional
      ai/
        provider.py    — TemplateProvider (default) + AnthropicProvider (optional)
        dispatcher.py  — Rescue AI panel query handler
        tools.py       — AI tool implementations (real DB queries)
      intelligence/
        provider.py           — ExplainableAIProvider for per-entity deep analysis
        sos_intelligence.py   — SOS-specific intelligence (Tamil-first, IN PROGRESS)
        harbor_intelligence.py
        boat_intelligence.py (may exist)
        trip_intelligence.py  (may exist)
    core/
      rate_limit.py    — In-memory sliding window (single-process, documented)
      security.py      — JWT + bcrypt
      deps.py          — FastAPI dependency injection

Rescue Dashboard (React/Vite)
  rescue-dashboard/src/
    pages/           — DashboardPagePremium, SOSAlertsPagePremium, IncidentsPage, etc.
    components/      — boats/, harbors/, incidents/, sos/, ui/
    api/             — client.js, auth.js, tracking.js, analytics.js, etc.
    context/         — AuthContext, ToastContext

CI/CD
  .github/workflows/ci.yml  — backend pytest, mobile flutter analyze+test, dashboard build, gitleaks
```

**Key model facts (never get these wrong):**
- `SOSAlert`: `triggered_at` is NOT NULL, `latitude`/`longitude` are NOT NULL,
  `client_uuid` auto-generated in `__init__`, `fisherman_id` aliased to `user_id`
- `SOSStatus` enum: `active`, `acknowledged`, `resolved`, `false_alarm`
- `LocationPing`: `user_id`, `latitude`, `longitude`, `recorded_at`, `accuracy_meters`,
  `battery_percent`
- `RiskIncident`: `fisherman_id`, `status` (8-state machine)
- `Trip`: `user_id`, `status` (TripStatus enum), `start_time`

**Key schema facts:**
- `DecisionSupport` (in `schemas/intelligence.py`): `recommendation`, `reason`,
  `evidence: List[DecisionEvidence]`, `confidence_score`, `priority`, `risk_level`,
  `suggested_action`, `alternative_recommendations`
- `SOSReport` (in `schemas/intelligence.py`): `alert_id`, `severity_assessment`,
  `resource_recommendation`, `response_priority`, `estimated_rescue_minutes`
- All Tamil fields added to schemas must be `Optional[str] = None` for backward
  compatibility — never make them required.

**Test fixture rules (never break these):**
- `SOSAlert` test fixtures MUST pass `triggered_at=datetime.utcnow()`,
  `latitude=<float>`, `longitude=<float>`
- Use `conftest.py` fixtures (`db`, `fisherman_user`, `operator_user`) — never
  create raw DB sessions in tests
- Test files live in `backend/tests/` — never modify existing test assertions
  unless a bug fix explicitly requires it, and document why

---

## CURRENT STATE (verified, 2026-07-25 + Module 2 audit)

**Test count**: 485 passed, 2 skipped (honest — no real AI/SMS credentials), 0 failed

**What is complete and working:**
- GPS tracking, offline-first sync, trip lifecycle
- Safety State Engine (deterministic, rule-based, server-authoritative)
- Live Weather Intelligence (Open-Meteo, real, verified)
- AI Explainability: TemplateProvider (verified) + AnthropicProvider (implemented, unverified)
- Human-believable AI: emotional tone, Tamil-first, coastal elder voice
- Rescue AI Panel: 7 intents, full explainability envelope, confidence scoring
- SOS 2.0: 11 emergency types, offline-first trigger
- 8-state Incident Engine with audit trail
- Family Portal: safety state + incident status
- Notification Engine: simulation (verified) + Twilio (implemented, unverified)
- Security: 7 audit findings closed, rate limiting, JWT, bcrypt
- CI pipeline: `.github/workflows/ci.yml` (defined, not yet run on GitHub)
- Demo Mode: `scripts/demo_mode.sh` (verified end-to-end)
- Early Warning: Tamil fields added (`what_changed_ta`, `why_it_matters_ta`,
  `recommended_action_ta`)
- Risk Prediction v2: GPS/boat/fuel caps, time-of-day factor, computed confidence
- Harbor Intelligence: real capacity field, honest confidence
- SOS Intelligence: taxonomy rewritten (Tamil-first 6-tuple), class body EXISTS
  but Tamil fields NOT YET returned in `SOSReport`

**What is NOT yet done (your work):**

---

## YOUR TASKS — EXECUTE IN THIS EXACT ORDER

### PHASE A — SOS Tamil Intelligence Layer (HIGHEST PRIORITY)

**Why first**: Tamil fishermen receive English-only SOS responses right now.
This is the most direct life-safety gap.

**A1. Extend `SOSReport` schema** (`backend/app/schemas/intelligence.py`)

Add these fields to `SOSReport` — all `Optional[str] = None` for backward compat:
```python
# Tamil-language fields — populated for all responses, not just Tamil requests
severity_reason_ta: Optional[str] = None
resource_recommendation_ta: Optional[str] = None
fisherman_message_ta: Optional[str] = None
priority_label_ta: Optional[str] = None
rescue_time_ta: Optional[str] = None
status_ta: Optional[str] = None
```

**A2. Rewrite `SOSIntelligenceService.evaluate()`**
(`backend/app/services/intelligence/sos_intelligence.py`)

The `_SOS_TYPE_MAP` and `_STATUS_TA` / `_PRIORITY_TA` dicts are already correct.
The class body needs to populate Tamil fields in the returned `SOSReport`.

The `evaluate()` method must:
1. Look up the 6-tuple from `_SOS_TYPE_MAP` using `alert.alert_type`
2. Extract: `risk_level, en_sev, en_rec, ta_sev, ta_rec, ta_fisherman_msg`
3. Call existing `_assess_severity`, `_recommend_resources`, `_assess_priority`
   (do NOT change their signatures or return types — they return `DecisionSupport`)
4. Call `_estimate_rescue_minutes`
5. Build Tamil rescue time string: `f"{minutes} நிமிடங்களில் உதவி வரும்"` or
   `"தூரம் தெரியவில்லை"` if None
6. Return `SOSReport` with ALL existing fields PLUS the new `_ta` fields

The `_assess_severity` method must also add Tamil battery/GPS warnings:
- Battery < 20%: `"Battery {pct}% — தொடர்பு விரைவில் துண்டிக்கப்படலாம்."`
- GPS accuracy > 200m: `"GPS துல்லியம் குறைவு (±{m}m) — தேடல் பரப்பு அதிகம்."`

**A3. Write `backend/tests/test_sos_tamil_intelligence.py`**

Cover:
- All 7 SOS types return correct Tamil fields (non-empty strings)
- `fisherman_message_ta` is calm/reassuring for fisherman-facing types
- Battery warning in Tamil when `battery_level_percent < 20`
- GPS warning in Tamil when `accuracy_meters > 200`
- `rescue_time_ta` is populated when harbor exists, `"தூரம் தெரியவில்லை"` when not
- `priority_label_ta` matches `_PRIORITY_TA` lookup
- `status_ta` matches `_STATUS_TA` lookup
- Backward compat: existing English fields still present and correct
- Unknown SOS type falls back gracefully (no crash, sensible defaults)

Test fixture pattern (copy exactly):
```python
from datetime import datetime
from app.models.sos import SOSAlert, SOSStatus

def make_alert(db, fisherman, alert_type="medical", battery=50, accuracy=10):
    alert = SOSAlert(
        user_id=fisherman.id,
        alert_type=alert_type,
        triggered_at=datetime.utcnow(),
        latitude=10.5,
        longitude=79.8,
        battery_level_percent=battery,
        accuracy_meters=accuracy,
        status=SOSStatus.active,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
```

---

### PHASE B — Version Bump (QUICK WIN, 10 minutes)

**Why**: Monitoring, release tracking, and API consumers see `"0.5.0"` everywhere.
The system is at V2 RC1.

**B1.** In `backend/app/main.py`, replace ALL occurrences of `"0.5.0"` with
`"2.0.0-rc1"` — in the `FastAPI(version=...)` constructor AND in every
`@app.get` handler that returns a `"version"` key.

**B2.** In `rescue-dashboard/package.json`, change `"version": "0.2.0"` to
`"version": "2.0.0-rc1"`.

**B3.** In `docs/RELEASE_READINESS_REPORT.md` §1, update the version note to
reflect `2.0.0-rc1` is now set.

Do NOT change any test that asserts a version string — check first with grep.

---

### PHASE C — Notification Retry Job

**Why**: A failed notification is recorded but never retried. A family member
can miss the SOS alert entirely if the first delivery fails. This breaks the
core family-awareness promise.

**C1. Add retry logic to `backend/app/services/notification_service.py`**

Add a function `retry_failed_notifications(db: Session) -> int` that:
1. Queries `FamilyNotification` rows where `delivery_status = "failed"` AND
   `retry_count < 3` AND `created_at > now - 24h` (don't retry old failures)
2. For each, calls the notification provider again
3. On success: sets `delivery_status = "delivered"`, increments `retry_count`
4. On failure: increments `retry_count`, updates `last_retry_at`
5. Returns count of successfully retried notifications
6. NEVER raises — all exceptions caught and logged

**C2. Add `retry_count` and `last_retry_at` fields to `FamilyNotification`
model** (`backend/app/models/notification_models.py`) — both nullable with
defaults (`retry_count = 0`, `last_retry_at = None`). Add as `Column` with
`default=0` / `nullable=True` so existing rows are unaffected.

**C3. Add Alembic migration** `backend/alembic/versions/024_notification_retry.py`:
```python
def upgrade():
    op.add_column('family_notifications',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('family_notifications',
        sa.Column('last_retry_at', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('family_notifications', 'last_retry_at')
    op.drop_column('family_notifications', 'retry_count')
```

**C4. Wire the retry job into `backend/app/worker.py`** — call
`retry_failed_notifications` on a 5-minute interval. If `worker.py` uses
a background thread or APScheduler, add it there. If it's a simple loop,
add it. Never block the main request path.

**C5. Write tests** in `backend/tests/test_notification_retry.py`:
- Failed notification gets retried and marked delivered on success
- Notification with `retry_count >= 3` is NOT retried
- Notification older than 24h is NOT retried
- Provider crash during retry increments `retry_count` but does not raise

---

### PHASE D — Rate Limiter Honesty Fix

**Why**: The current in-memory rate limiter resets on restart and doesn't work
behind multiple workers. It's documented as a known limitation but the
documentation is buried. The fix is to make the limitation visible at runtime
and add a clear upgrade path.

**D1.** In `backend/app/core/rate_limit.py`, add a startup warning log:
```python
import logging as _log
_log.getLogger(__name__).warning(
    "Rate limiter is single-process in-memory. "
    "In a multi-worker deployment, each worker enforces its own independent limit. "
    "For cluster-safe rate limiting, set RATE_LIMIT_BACKEND=redis and configure REDIS_URL."
)
```
Log this once at module import time (not per-request).

**D2.** In `backend/app/config.py`, add two optional settings:
```python
rate_limit_backend: str = "memory"   # "memory" | "redis"
redis_url: str | None = None
```

**D3.** In `rate_limit.py`, if `settings.rate_limit_backend == "redis"` and
`settings.redis_url` is set, use Redis for the sliding window. Use `httpx` or
the standard `redis` package if already in requirements. If neither is
available, log a warning and fall back to memory. Never crash on missing Redis.

**D4.** Add `redis>=5.0.0` to `requirements.txt` as an optional dependency
with a comment: `# Optional: required only for RATE_LIMIT_BACKEND=redis`.

**D5.** Update `docs/SECURITY.md` to document the Redis upgrade path.

---

### PHASE E — Dependency Security

**Why**: `python-jose` has known CVEs. `pip audit` is not in CI.

**E1. Add `pip-audit` to CI** (`.github/workflows/ci.yml`), in the `backend`
job, after `pip install -r requirements.txt`:
```yaml
- name: Audit dependencies for known CVEs
  run: pip install pip-audit && pip-audit -r requirements.txt --ignore-vuln PYSEC-2022-42969
  continue-on-error: true  # warn, don't block, until python-jose is replaced
```
Use `continue-on-error: true` because `python-jose` has a known CVE that
cannot be fixed until the migration to `PyJWT` is done. This makes the
vulnerability visible in CI without blocking the build.

**E2. Add `PyJWT>=2.8.0` to `requirements.txt`** alongside `python-jose`
(do NOT remove `python-jose` yet — it may have callers). Add a comment:
`# TODO: migrate from python-jose to PyJWT — see docs/SECURITY.md`.

**E3. In `backend/app/core/security.py`**, read the current implementation.
If it uses `python-jose`, add a comment block at the top:
```python
# MIGRATION NOTE: This module currently uses python-jose (known CVE risk).
# PyJWT is now in requirements.txt. Migration path:
#   1. Replace jose.jwt.encode/decode with jwt.encode/decode (PyJWT API)
#   2. Update exception handling: jose.JWTError -> jwt.InvalidTokenError
#   3. Remove python-jose from requirements.txt
# Do NOT migrate in this pass — test coverage must be verified first.
```

**E4.** Update `docs/SECURITY.md` to document the CVE, the migration plan,
and the CI audit step.

---

### PHASE F — Dashboard Tests (Vitest)

**Why**: The rescue dashboard has zero automated tests. Any regression in the
operator UI is invisible. Operators use this dashboard to manage life-safety
incidents.

**F1. Install Vitest** in `rescue-dashboard/`:
Add to `package.json` devDependencies:
```json
"vitest": "^1.6.0",
"@testing-library/react": "^16.0.0",
"@testing-library/jest-dom": "^6.4.0",
"@testing-library/user-event": "^14.5.0",
"jsdom": "^24.0.0"
```

Add to `package.json` scripts:
```json
"test": "vitest run",
"test:watch": "vitest"
```

Add `vitest.config.js`:
```js
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
  },
})
```

Add `rescue-dashboard/src/test/setup.js`:
```js
import '@testing-library/jest-dom'
```

**F2. Write `rescue-dashboard/src/test/formatters.test.js`**

Test `src/utils/formatters.js` — every exported function. These are pure
functions with no React dependency, so they're the safest first tests.
Cover: safety state formatting, freshness label formatting, date formatting,
any null/undefined inputs (must not throw).

**F3. Write `rescue-dashboard/src/test/SafetyStateBadge.test.jsx`**

Test the safety state badge component (if it exists in `components/ui/`).
Cover: CRITICAL renders red, SAFE renders green, UNKNOWN renders gray (not
green — this was a real bug found in the safety semantics audit), unknown
string input renders a safe fallback.

**F4. Write `rescue-dashboard/src/test/api.test.js`**

Mock `src/api/client.js` and test that:
- `auth.js` login sends correct payload
- `tracking.js` get-location handles 404 gracefully (returns null, not throw)
- `analytics.js` handles network error gracefully

**F5. Add `npm test` to CI** (`.github/workflows/ci.yml`), in the `dashboard`
job, after `npm install` and before `npm run build`:
```yaml
- name: Run dashboard tests
  run: npm test
```

---

### PHASE G — Fleet Query Batching

**Why**: `get_high_risk_vessels` and `get_offline_vessels` in
`backend/app/services/ai/tools.py` loop over active trips one by one,
calling `SafetyEngine.evaluate()` per fisherman. At 100+ concurrent trips
this becomes slow. The fix is to batch the DB queries.

**G1. Read `backend/app/services/ai/tools.py` fully before touching it.**

**G2.** In `get_high_risk_vessels` and `get_offline_vessels`, replace the
per-fisherman loop with a batched approach:
1. Fetch all active trips in ONE query with a JOIN to users
2. Fetch all relevant location pings in ONE query using `user_id IN (...)`
3. Fetch all active SOS alerts in ONE query using `user_id IN (...)`
4. Fetch all open incidents in ONE query using `fisherman_id IN (...)`
5. Build a dict keyed by `user_id` for O(1) lookup
6. Evaluate safety state using the pre-fetched data (no additional DB calls
   per fisherman)

**Important**: Do NOT change the return schema of these functions. The
callers (`dispatcher.py`, tests) depend on the exact dict structure.
Only the internal implementation changes.

**G3.** Add a test in `backend/tests/test_ai_module2_audit.py` (append,
don't create a new file) that creates 5 fishermen with active trips and
calls `get_high_risk_vessels` — assert it returns in under 1 second and
returns the correct structure.

---

### PHASE H — Mobile Sync Service Tests

**Why**: The offline sync service is the core promise of the system
("works with zero signal at sea") but has no dedicated tests.

**H1. Write `mobile/test/sync_service_test.dart`**

Cover:
- Pending GPS pings in the local SQLite outbox are sent to the API on sync
- Pending SOS alerts in the outbox are sent with correct fields
  (`alert_type`, `triggered_at`, `latitude`, `longitude`)
- A network failure during sync does NOT delete the outbox entry
  (it stays pending for the next sync)
- Duplicate `client_uuid` entries are not re-sent (idempotency)
- Sync with empty outbox completes without error

Use `mockito` or `mocktail` for HTTP mocking (check `pubspec.yaml` for
what's already there — do NOT add a new dependency if one exists).

**H2. Write `mobile/test/location_service_test.dart`**

Cover:
- Location service returns a `LocationPoint` with non-null lat/lng
- Location service handles permission denied gracefully (returns null,
  does not throw)
- Accuracy and battery fields are populated when available

---

### PHASE I — Early Warning Tamil Reasons Fix

**Why**: `what_changed_ta` in `early_warning.py` currently just copies
English reason strings. Tamil fishermen see English text in the most
critical warning field.

**I1. In `backend/app/services/early_warning.py`**, update the
`what_changed_ta` field to translate the category names to Tamil:

```python
_CATEGORY_TA = {
    "weather": "வானிலை",
    "distance": "துறைமுகத்திலிருந்து தூரம்",
    "communication": "தொடர்பு இல்லை",
    "incident": "சம்பவம் திறந்துள்ளது",
    "battery": "battery குறைவு",
}
```

Replace the `what_changed_ta` assignment with:
```python
what_changed_ta = "; ".join(
    _CATEGORY_TA.get(cat, cat) for cat in sorted(fired_categories)
)
```

This gives Tamil fishermen Tamil category names instead of English reason
strings. The English `what_changed` field is unchanged.

**I2.** Add a test in `backend/tests/test_ai_module2_audit.py` (append)
that calls `early_warning.evaluate(..., language="ta")` and asserts
`what_changed_ta` contains Tamil text (not English reason strings).

---

### PHASE J — Final Documentation and Status Update

**Why**: `GOD_MODE_STATUS.md` and `RELEASE_READINESS_REPORT.md` are the
authoritative status documents. They must reflect the actual state after
all phases above are complete.

**J1. Update `docs/GOD_MODE_STATUS.md`**:
- Update §0 "Final Release Engineering" to add a new entry for this session
- Update §13 "Test Results" with the new test count
- Update §15 "Known Limitations" — remove items that are now fixed
- Update §22 "Final Production-Readiness Assessment" — honest assessment
  of what changed

**J2. Update `docs/RELEASE_READINESS_REPORT.md`**:
- Update §1 version to `2.0.0-rc1`
- Update §3 test results
- Update §12 known limitations
- Update §16 release recommendation

**J3. Update `CHANGELOG.md`** at the project root with a new entry:
```markdown
## [2.0.0-rc1] — YYYY-MM-DD
### Added
- SOS Tamil Intelligence Layer: all 7 SOS types return Tamil fields
- Notification retry job: failed notifications retried up to 3 times
- Dashboard Vitest test suite: formatters, safety badge, API client
- Mobile sync service tests and location service tests
- pip-audit in CI for dependency CVE scanning
- Redis-backed rate limiter option (RATE_LIMIT_BACKEND=redis)
- Fleet query batching in AI tools (O(N) → O(1) DB calls)
### Fixed
- Early warning Tamil reasons now use Tamil category names
- Version bumped from 0.5.0 to 2.0.0-rc1 everywhere
### Security
- PyJWT added alongside python-jose with migration path documented
- pip-audit added to CI (continue-on-error until python-jose migrated)
```

---

## EXECUTION RULES — READ BEFORE WRITING A SINGLE LINE

### Before every file write:
1. **Read the current file** — never write blind
2. **Check all callers** — grep for the function/class name before changing
   its signature
3. **Check existing tests** — grep for the function name in `tests/` before
   changing behavior

### Schema changes:
- New fields on Pydantic models: ALWAYS `Optional[X] = None`
- New columns on SQLAlchemy models: ALWAYS `nullable=True` or `default=value`
- New Alembic migrations: ALWAYS additive (add_column, create_table) — never
  drop_column or alter_column in this pass

### Test rules:
- Never modify existing test assertions
- New tests go in new files or are appended to existing files
- Every new test must be independent (no shared mutable state)
- Use `conftest.py` fixtures — never create raw DB sessions
- `SOSAlert` fixtures MUST include `triggered_at`, `latitude`, `longitude`

### Tamil language rules:
- Simple vocabulary — a 60-year-old fisherman with basic literacy must
  understand it
- Calm tone — never create panic, even for CRITICAL alerts
- Fisherman-facing: reassuring ("உதவி வருகிறது" — help is coming)
- Operator-facing: direct, action-oriented, no softening
- Numbers always stated in both languages

### Safety rules:
- SOS trigger endpoint MUST never be rate-limited
- Notification failure MUST never fail the SOS request
- AI explanation failure MUST never fail the safety state response
- Every `except Exception` block MUST log the error (never silent swallow)

### Version rules:
- Search for ALL occurrences of the old version string before replacing
- Check test files for version assertions before changing

---

## VERIFICATION CHECKLIST

After completing all phases, verify:

```bash
# Backend
cd backend
python -m pytest tests/ -q
# Expected: >= 510 passed (485 + ~25 new), 2 skipped, 0 failed

# Mobile
cd mobile
flutter gen-l10n
flutter analyze --no-fatal-infos --fatal-warnings
flutter test
# Expected: 0 errors, >= 14 tests passed (10 + 4 new)

# Dashboard
cd rescue-dashboard
npm install
npm test
npm run build
# Expected: all tests pass, build succeeds

# Manual spot checks
# 1. SOSReport for "medical" type has non-empty fisherman_message_ta
# 2. SOSReport for "sinking" type has fisherman_message_ta containing "life jacket"
# 3. Early warning with weather+distance categories has Tamil what_changed_ta
# 4. /health endpoint returns version "2.0.0-rc1"
# 5. Rate limiter logs a warning at startup about single-process limitation
```

---

## WHAT SUCCESS LOOKS LIKE

When all phases are complete:

- A Tamil fisherman triggering a "sinking" SOS receives:
  - English: "Vessel sinking — life-threatening emergency."
  - Tamil: "படகு மூழ்குகிறது — உயிருக்கு ஆபத்தான நிலை."
  - Fisherman message: "உடனே life jacket போடுங்கள். படகை விட வேண்டாம். உதவி வருகிறது."
  - Rescue time in Tamil: "48 நிமிடங்களில் உதவி வரும்"

- A failed family notification is automatically retried within 5 minutes,
  up to 3 times, with the result recorded honestly.

- The rescue dashboard has automated tests that catch regressions before
  they reach operators managing real emergencies.

- CI runs `pip-audit` and surfaces any new CVEs before they ship.

- The fleet map loads in under 500ms even with 100 active trips.

- Every status document reflects the true, verified state of the system.

This is a system that protects fishermen's lives. Build it like one.
