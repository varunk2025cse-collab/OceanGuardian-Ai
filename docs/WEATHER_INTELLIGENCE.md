# Weather Intelligence

`backend/app/services/weather_service.py` — V2 core build Phase 10.

## What changed from V1

V1's `WEATHER_PROVIDER=open-meteo` setting existed but nothing ever read it
(`docs/V1_AUDIT.md` §6/§9) — all weather came from a manually-seeded static
`weather_alerts` table. That table is still used (it's the right source
for the Safety Engine's radius-based alert lookup — see
`docs/SAFETY_STATE_ENGINE.md`), but there is now also a genuinely live
provider for point-in-time current conditions.

## Provider abstraction

```
WeatherProvider (interface)
  -> OpenMeteoProvider   real HTTP calls to api.open-meteo.com (wind/rain/
                         pressure/visibility) + marine-api.open-meteo.com
                         (wave height/direction). No API key required.
                         Verified live in this environment (network access
                         confirmed; tests hit the real endpoint).
  -> SimulatedProvider   deterministic synthetic data, labeled
                         source="SIMULATED", used only when
                         WEATHER_PROVIDER=simulated is explicitly set.
```

Selection: `get_weather_provider()` reads `settings.weather_provider`
("open-meteo" default, or "simulated").

## Failure handling

If the real provider's HTTP calls fail (network error, timeout,
non-200), `WeatherObservation.available=False` with `unavailable_reason`
set — the API never fabricates numbers to fill the gap. Forecast and
marine calls are independent; a boat outside marine-data coverage but
with valid wind data still gets a partial, honest result.

## API

`GET /api/v2/weather/live?lat=&lon=` — any authenticated user. Distinct
from `/api/v1/weather/active` (the static hazard-advisory feed, unchanged).

## Status: IMPLEMENTED (real, not simulated, by default)

Verified with a live network call in `tests/test_god_mode_safety_incident_ai.py::test_live_weather_endpoint_returns_observation`.
Known limitation: no caching layer — every `/live` call is a fresh
upstream request. Fine at current scale; worth adding a short TTL cache
before high-traffic production use.
