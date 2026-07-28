# Safety State Engine

Deterministic, rule-based, server-authoritative (`backend/app/services/safety_engine.py`).
V2 core build Phase 9 (states) + Phase 11 (weather/harbor-distance inputs).

## Why deterministic, not ML/LLM

Safety-critical scoring must be explainable, testable, and available even
when an external AI provider is down. The engine computes a 0-100 score
from real signals only; AI (`docs/AI_ARCHITECTURE.md`) only narrates this
output afterward — it never computes it.

## States (two independent axes — never merged)

**Safety state** — `SAFE | MONITOR | CAUTION | HIGH_RISK | CRITICAL | UNKNOWN`
Score thresholds are configurable (`app/config.py`:
`safety_score_monitor/caution/high_risk/critical`, defaults 21/41/61/81).
`UNKNOWN` means no trip is currently in progress — silence is never
presented as "safe".

**Communication state** — `ONLINE | OFFLINE | UNKNOWN`
Derived from location freshness (`tracking_service.compute_freshness`):
LIVE/RECENT → ONLINE, LAST_KNOWN/STALE → OFFLINE, no data → UNKNOWN.

A vessel can legitimately be `HIGH_RISK` + `ONLINE`, or `MONITOR` +
`OFFLINE` — the two states are computed and returned independently.

## Inputs (real only — nothing invented)

| Factor | Source | Weight |
|---|---|---|
| Active SOS | `sos_alerts` | Overrides everything → CRITICAL (100) |
| Trip flagged EMERGENCY | `trips.status` | +60 |
| Location freshness STALE | `location_pings` | +30 |
| Location freshness LAST_KNOWN | `location_pings` | +15 |
| No location data ever | `location_pings` | +20 |
| Open incident for this fisherman | `risk_incidents` | +25 |
| Poor GPS accuracy (>100m) | `location_pings.accuracy_meters` | +5 |
| Low battery (≤15%) | `location_pings.battery_percent` (real telemetry — V2 core build Step 3) | +10 |
| Nearby active weather warning/danger | `weather_alerts` table (same radius lookup as `/api/v1/risk/score`) | +25 |
| Nearby active weather advisory | `weather_alerts` table | +10 |
| Far from nearest harbor (>40km) | `harbors` table, haversine | +15 |
| Moderately far from harbor (20-40km) | `harbors` table, haversine | +5 |

Weather/harbor lookups are DB-only (no live HTTP call) so fleet-wide
evaluation stays fast — see `docs/WEATHER_INTELLIGENCE.md` for why live
conditions are a separate, opt-in endpoint.

## API

- `GET /api/v2/safety/` — the logged-in fisherman's own state
- `GET /api/v2/safety/{fisherman_id}` — self / operator / linked family only
- `GET /api/v2/safety/fleet/summary` — operator-only, every in-progress trip

## Early Warning (Phase 13)

`app/services/early_warning.py` — fires when ≥2 independent risk
categories (weather, distance, communication, incident, battery) are true
in the **same** evaluation. Honest scope note: this is a snapshot
classifier, not a trend detector — it does not track "getting worse over
time" (that needs persisted evaluation history, a real follow-on, not
faked here).

## Status: IMPLEMENTED

Real computation, 19+ passing tests (`tests/test_god_mode_safety_incident_ai.py`).
Not implemented: historical trend detection, ML-based risk modeling
(deliberately out of scope per the governing brief).
