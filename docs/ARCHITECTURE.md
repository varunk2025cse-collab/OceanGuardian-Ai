# OceanGuardian AI — MVP Architecture

## System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FLUTTER MOBILE APP                          │
│                                                                       │
│  ┌──────────────┐   ┌───────────────┐   ┌──────────────────────┐    │
│  │  Screens     │   │   Services    │   │   Local SQLite DB    │    │
│  │  (UI layer)  │──▶│  - Auth       │──▶│   pending_locations  │    │
│  │              │   │  - Location   │   │   pending_sos        │    │
│  │  SOS / Map / │   │  - SOS        │   │   cache_kv (weather, │    │
│  │  Weather /   │   │  - Sync       │   │     market, schemes,  │    │
│  │  Family /    │   │  - Reference  │   │     family status)    │    │
│  │  Market /    │   │    Data       │   └──────────────────────┘    │
│  │  Schemes     │   └───────┬───────┘                               │
│  └──────────────┘           │  HTTPS + JWT (when signal available)  │
└──────────────────────────────┼───────────────────────────────────────┘
                                │
                                ▼
                  ┌──────────────────────────┐
                  │   FastAPI Backend (REST)  │
                  │   /api/v1/...             │
                  │   - auth (JWT)             │
                  │   - locations (sync)       │
                  │   - sos (idempotent)       │
                  │   - weather / market /     │
                  │     schemes / family       │
                  └─────────────┬──────────────┘
                                │  SQLAlchemy
                                ▼
                  ┌──────────────────────────┐
                  │      PostgreSQL 16        │
                  │  users, location_pings,   │
                  │  sos_alerts, family_links,│
                  │  weather_alerts,          │
                  │  market_prices,           │
                  │  govt_schemes             │
                  └────────────────────────────┘

   External: OpenStreetMap tile servers (map display only — never on the
   critical path for GPS capture, SOS triggering, or sync; those are
   pure app ↔ backend ↔ database with no third-party dependency).
```

## Why offline-first, end to end

The entire point of this product is that it has to work where signal
doesn't reach. That requirement shaped three concrete decisions:

1. **Write-local-first, sync-later for everything safety-critical.**
   GPS fixes and SOS triggers are written to on-device SQLite the instant
   they happen. A network call is *attempted* afterward, but its success
   or failure never blocks the user-facing "saved" confirmation.

2. **Idempotent sync via client-generated UUIDs.** Every offline record
   carries a `client_uuid` minted on the device at capture time. The
   backend treats re-sending an already-seen `client_uuid` as a no-op
   (return the existing row) rather than an error or a duplicate. This
   means the sync logic can be dumb and aggressive — retry on every
   connectivity blip, retry on a timer, retry after app restart — without
   ever risking duplicate SOS alerts or a corrupted GPS trail.

3. **Cache-first reads for reference data.** Weather, market prices,
   schemes, and family status are fetched live when possible and written
   to a local cache either way. When offline, the screen serves the last
   cached version with a visible "offline" badge, rather than a blank
   error screen.

## SOS data flow (the one path that matters most)

```
Fisherman taps SOS
        │
        ▼
Get GPS fix (8s timeout, falls back to last-known if no fresh fix)
        │
        ▼
Write to local SQLite outbox  ───────────────►  ALWAYS SUCCEEDS
        │                                       (this is "SOS sent" to the user)
        ▼
Attempt live POST /api/v1/sos/trigger
        │
   ┌────┴────┐
   ▼         ▼
Success   No signal
   │         │
   ▼         ▼
Mark      Stays in outbox;
synced    SyncService retries
          every 30s AND on
          every connectivity
          change until it
          lands
        │
        ▼
Backend: idempotent on client_uuid (button mashed 5x ⇒ 1 alert)
        │
        ▼
sos_service.notify_emergency_contacts() fans out to
emergency contact + (Stage 2) rescue dashboard / Coast Guard webhook
```

## Data model summary

| Table | Purpose | Key constraint |
|---|---|---|
| `users` | Fishermen and family accounts (one table, `role` column) | unique `phone_number` |
| `location_pings` | GPS trail | unique `client_uuid` (sync idempotency) |
| `sos_alerts` | Distress alerts + lifecycle status | unique `client_uuid` |
| `family_links` | Which family account watches which fisherman | unique `(fisherman_id, family_user_id)` |
| `weather_alerts` | Hazard zones (circle: center + radius) | — |
| `market_prices` | Daily fish prices by species/region | — |
| `govt_schemes` | Government scheme directory | — |

Full DDL: `backend/schema.sql` (generated from the SQLAlchemy models —
see `backend/generate_schema_sql.py` — so it can't drift from the code).

## Tech stack (as specified)

| Layer | Choice | Why it fits the MVP |
|---|---|---|
| Mobile | Flutter | Single codebase for Android + iOS, mature offline/SQLite story |
| Backend | FastAPI | Async-ready, auto-generated OpenAPI docs, fast to extend |
| Database | PostgreSQL | Relational integrity for safety data, mature ops tooling |
| Offline storage | SQLite (`sqflite`) | Battle-tested on-device store, zero server dependency |
| Maps | OpenStreetMap (`flutter_map`) | No API key, no per-request cost — important at fleet scale |
| Auth | JWT (access + refresh) | Stateless, works across the FastAPI + mobile boundary cleanly |

## Explicitly out of scope for this MVP

These were in the original platform vision but are deliberately deferred
so the MVP stays buildable and testable in one pass:

- Voice AI / multilingual voice assistant
- AI fish/species prediction, demand forecasting
- IoT boat health monitoring, satellite communication layer
- Offline map *tile* caching and turn-by-turn navigation
- Rescue/Coast Guard operator dashboard (the API supports it — `GET
  /sos/active` — but no dedicated UI ships in this MVP)
- Multi-language beyond English/Tamil (the i18n plumbing supports adding
  more `.arb` files cheaply when needed)

This list is the natural roadmap for the phases after the MVP is validated
with real fishermen.
