# Navigation AI

`backend/app/services/geo.py` (bearing/compass math), `harbor.py` (nearest
harbor + bearing), `safety_engine.py` (integration into safety reasoning),
`services/ai/tools.py::get_navigation_guidance` (AI tool layer).

## What this is

A straight-line compass bearing and distance from a fisherman's current
(or last known) position to the nearest known safe harbor — the exact
calculation a fisherman could do by hand with a paper chart and a
compass, computed for them and surfaced automatically, especially when
risk is elevated.

## What this is explicitly NOT

Not route optimization. It does not account for obstacles, shallows,
restricted zones, currents, or shipping lanes — that would require
bathymetry and AIS/traffic data this platform does not have access to.
Presenting this as a "navigate me there safely around hazards" feature
would violate the project's own rule against claiming capability that
isn't real. The bearing is honest: "this direction, this far, to a known
harbor" — nothing more.

## Where it shows up

- **`GET /api/v2/safety/`** (and `/{fisherman_id}`, `/fleet/summary`) —
  every safety evaluation includes `nearest_harbor_name`,
  `nearest_harbor_km`, `nearest_harbor_bearing`, `nearest_harbor_direction`
  (8-point compass label), `nearest_harbor_eta_minutes`. All null when
  there's no location data — never a fabricated fallback.
- **Safety Engine reasoning** — when a vessel is far from any known
  harbor (>40km), the reason text names the harbor and bearing, e.g.
  *"Vessel is far from the nearest known harbor (~55km, Nagapattinam
  Harbor bearing NE)."*
- **`POST /api/v2/harbor/nearest`** / **`/emergency-harbor`** — the
  existing harbor-lookup endpoints now include `bearing_degrees` and
  `compass_direction` in their response.
- **AI tool `get_navigation_guidance`** + dispatcher intent
  `navigation_guidance` — the Rescue AI panel and any future assistant
  surface can ask "which way should this vessel go" and get a real,
  computed answer.
- **Mobile home screen** — a compass-arrow card (`_NavigationCard` in
  `home_dashboard_screen.dart`) shows the harbor name, a rotated compass
  arrow, distance, and ETA, reusing the same safety-state fetch (no extra
  network call).

## A bug this work found and fixed

`HarborResponse` (the API schema returned by every harbor endpoint)
declared `latitude`, `longitude`, `state`, `district`, and `harbor_type`
as required strings/floats — but the underlying `Harbor` database model
allows all of them to be `NULL` ("legacy Phase 2 columns kept for v1 API
compatibility"). Any harbor missing one of these fields crashed the
endpoint with a 500. Found via this feature's own test suite
(`tests/test_navigation_ai.py`), fixed by making the schema match the
model's actual nullability.

## Status: IMPLEMENTED, tested

8 new backend tests (`tests/test_navigation_ai.py`) covering the bearing
math itself, the harbor endpoint integration, Safety Engine integration,
the AI tool/dispatcher intent, and its authorization boundary. 244/244
backend tests passing (up from 236). Mobile: `flutter analyze` clean,
10/10 tests passing.

## Natural next steps (not built this pass — noted, not silently dropped)

- Surface the same guidance on the family screen (a family member watching
  an elevated-risk trip would benefit from the same "which way to safety"
  context).
- A dedicated "Nearest Safe Harbor" button on the Rescue AI panel per
  vessel (the tool/intent exist; only a one-click UI trigger is missing).
