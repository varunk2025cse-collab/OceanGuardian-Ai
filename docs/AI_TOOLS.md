# AI Tool Layer

`backend/app/services/ai/tools.py` — V2 core build Phase 18.

Every function is a controlled, authorized read against the existing
service layer. No tool executes raw SQL, accepts an unvalidated
identifier without an authorization check, or touches the filesystem.
This is the literal implementation of "AI must retrieve facts from
controlled backend tools, never direct DB access."

## Tools

| Tool | Authorization | Backing service |
|---|---|---|
| `get_boat_status` | operator | `boats` table |
| `get_trip_status` | operator | `trip_service` |
| `get_latest_location` | self / operator / linked family | `tracking_service.TrackingService` |
| `get_location_history` | self / operator / linked family | `tracking_service.TrackingService` |
| `get_location_freshness` | self / operator / linked family | `tracking_service.compute_freshness` |
| `get_weather` | any authenticated user | `weather_service` (live) |
| `get_weather_alerts` | any authenticated user | `weather_alerts` table |
| `get_safety_state` | operator | `safety_engine.SafetyEngine` |
| `get_risk_factors` | operator | `safety_engine.SafetyEngine` |
| `get_active_incidents` | operator | `incident_service.IncidentService` |
| `get_incident` | self / operator / linked family (per-incident) | `incident_service.IncidentService` |
| `get_high_risk_vessels` | operator | `tracking_service` + `safety_engine` |
| `get_offline_vessels` | operator | `tracking_service` |
| `get_active_sos` | operator | `sos_alerts` table |
| `get_rescue_resources` | operator | `harbors` table (nearest harbors — OceanGuardian does not model rescue vessels/personnel as of this build, so this is deliberately harbor infrastructure only, not a fabricated resource roster) |
| `generate_incident_summary` | per `get_incident` | `incident_service` + `ai.provider` |
| `get_navigation_guidance` | self / operator / linked family | `harbor.HarborService` (docs/NAVIGATION_AI.md) |

Every function raises `fastapi.HTTPException` on an authorization failure
— the same behavior as the REST endpoints wrapping the same services, so
the AI layer can never see more than a human caller with the same role
could.

## Status: IMPLEMENTED

Covered by `tests/test_god_mode_safety_incident_ai.py` (AI query /
authorization tests) and indirectly by every service-layer test these
tools wrap.
