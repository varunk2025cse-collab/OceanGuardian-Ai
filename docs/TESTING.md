# Testing Strategy

## Current results (last full run, this session)

```
Backend:    236 passed, 2 skipped   (pytest tests/ -q)
Mobile:     flutter analyze --no-fatal-infos --fatal-warnings → 0 issues
            flutter test → 10 passed
Dashboard:  npm run build → succeeds (no test framework — see below)
```

## Backend (`backend/tests/`, pytest)

~30 files. Notable suites beyond the original MVP/Phase 2/Phase 5 tests:

| File | Covers |
|---|---|
| `test_core_tracking.py` | Trip state machine, tracking fleet/history authorization, freshness |
| `test_god_mode_safety_incident_ai.py` | Safety engine, weather endpoint, incident engine, SOS 2.0, AI dispatcher, notification dedup |
| `test_ai_provider_failure_handling.py` | AnthropicProvider degrades to template on auth failure/timeout/malformed response/rate limit — all mocked; 1 real-credential test, skipped without `ANTHROPIC_API_KEY` |
| `test_notification_provider_failure_handling.py` | TwilioSmsProvider failure handling — mocked; 1 real-credential test, skipped without Twilio credentials |
| `test_failure_injection.py` | The 10 deliberate failure scenarios (weather outage, AI outage, notification outage, stale GPS, out-of-order GPS, duplicate SOS, etc.) |
| `test_safety_semantics_audit.py` | Regression tests for two real bugs found during the safety-semantics audit (see below) |
| `test_e2e_golden_path.py` | The full 20-stage scenario in one continuous test |
| `test_rate_limit.py` | Rate limiter unit tests (disabled during the main suite via `ENVIRONMENT=test`) |
| `test_system_info.py` | Demo-mode banner backing endpoint |

### The 2 skipped tests — why, and how to un-skip them

```
test_anthropic_live_call_if_configured   — export ANTHROPIC_API_KEY
test_twilio_live_send_if_configured      — export TWILIO_ACCOUNT_SID,
                                            TWILIO_AUTH_TOKEN,
                                            TWILIO_FROM_NUMBER,
                                            TWILIO_TEST_TO_NUMBER
```

These are real integration tests, not disabled-and-forgotten — if you have
credentials, exporting them makes these run for real and prove the
provider actually works end-to-end. Without credentials, skipping is the
honest outcome (see `docs/AI_ARCHITECTURE.md`, `docs/NOTIFICATIONS.md`).

### Bugs found and fixed via this testing pass

Two real, safety-relevant bugs were found and fixed while building this
test suite (both have regression tests):

1. **SOS trigger failed the whole request if the notification provider
   raised**, even though the SOS alert was already safely persisted —
   found via `test_failure_injection.py`, fixed in `app/routers/sos.py`
   (incident creation and notification dispatch are now individually
   isolated with try/except; the alert itself is never affected).
2. **A fisherman with no location data was labeled `risk_label="safe"`**
   (score=0, green) on the operator's Fishermen list — an absence of data
   presented as an affirmative safety claim. Found via the Phase G safety
   semantics audit, fixed in `app/routers/admin.py` (now `"unknown"`,
   score=-1) and in the dashboard's `RiskBadge` component (which had a
   matching bug: any unrecognized label fell back to the "safe" style).

## Mobile (`mobile/test/`, `flutter test`)

| File | Covers |
|---|---|
| `local_db_service_test.dart` | Offline outbox sync-status/backoff, ordering (in-memory SQLite via `sqflite_common_ffi`) |
| `trip_test.dart` | Trip model parsing, `isInProgress` state logic |
| `sos_alert_test.dart` | Emergency-type taxonomy round-trip through DB/API JSON |
| `widget_test.dart` | App boots to splash screen |

Singleton-service architecture (documented in `docs/V1_AUDIT.md`) limits
how deeply services can be unit-tested without a larger DI refactor — out
of scope for this build; `flutter analyze` + these targeted tests are the
current coverage.

## Dashboard (`rescue-dashboard/`)

No test framework exists yet (`docs/V1_AUDIT.md` §7 — a pre-existing gap,
not introduced by this build). `npm run build` is the current smoke test —
it fails on type errors, broken imports, and build-time issues, which
catches a meaningful class of regressions even without unit tests.

## CI

All of the above runs automatically on every push/PR — see `docs/CI.md`.
