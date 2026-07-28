# Demo Mode

One-command scenario runner: `scripts/demo_mode.sh` (bash — verified,
see below) or `scripts/demo_mode.ps1` (PowerShell — same logic, written
against the same verified backend/demo_seed.py, but the PowerShell
orchestration wrapper itself was not separately dry-run in this session;
if something in the PowerShell process-management differs, the Python/API
layer it drives is proven correct, so a fix there would be narrowly
scoped).

```bash
bash scripts/demo_mode.sh
# or, on Windows PowerShell:
.\scripts\demo_mode.ps1
```

## What it actually does (verified this session, real run, real output)

1. Verifies `python`/`node` are available, prefers `backend/.venv` if present.
2. Points the backend at a **dedicated demo database**
   (`backend/demo_mode.db`) — never touches your regular dev database.
3. Sets `SEED_DEMO_DATA=true` and `DEMO_MODE=true` for this run only
   (never written to `.env`, never persisted).
4. Runs `seed.py` — reference data (harbors, weather alerts, market
   prices) + the demo operator account.
5. Starts the backend (`uvicorn`) in the background, waits for `/health`.
6. Runs `backend/demo_seed.py`, which drives the **real running API**
   over HTTP (not raw DB inserts) to:
   - register a demo fisherman + family member, link them
   - create a boat and start a trip
   - submit a 5-point GPS trail via the real offline-sync endpoint
   - call the **real** live weather endpoint (Open-Meteo — verified in
     this session's run: `source=open-meteo wind=17.3km/h wave=0.48m`)
   - fetch the real computed safety state
   - trigger a real SOS (`ENGINE_FAILURE`), which auto-creates a real
     incident and a real (simulated-delivery) family notification
   - log in as the demo operator, view the incident on `/api/v2/incidents/active`,
     and acknowledge it
7. Best-effort starts the rescue dashboard dev server (`npm run dev`) —
   verified reachable on port 3000 in this session's run.
8. Prints every access URL and every demo credential.

## Verification record (this session)

```
Backend health:      200 OK
system-info:          demo_mode=true, weather_provider=open-meteo,
                      ai_provider=template, notification_provider=simulation
demo_seed.py:         all 8 steps completed against a live server
                      (fisherman+family created, boat+trip created,
                      5/5 GPS points accepted, live weather fetched,
                      safety_state=MONITOR computed, SOS #1 triggered,
                      incident #1 created and acknowledged by the operator)
Dashboard:            200 OK on http://localhost:3000
Re-run (idempotency): confirmed — second run logs into existing accounts,
                      ends the prior trip, starts a fresh one, succeeds
```

## Demo accounts

| Role | Phone | Password |
|---|---|---|
| Fisherman | `+911111000001` | `Demo@1234` |
| Family | `+911111000002` | `Demo@1234` |
| Operator | `+911234567890` | `rescue123` |

## Mobile app

Not started by the script — it needs a connected device or emulator,
which this environment doesn't have. Run it yourself:

```
cd mobile
flutter run --dart-define=OG_API_BASE_URL=http://10.0.2.2:8000   # Android emulator
```

## DEMO / SIMULATION MODE indicator

`GET /api/v1/system-info` (unauthenticated, no secrets) reports
`demo_mode` and which providers are simulated. Both the rescue dashboard
(`SystemModeBanner` component) and the mobile app
(`SystemModeBanner` widget) poll this and render a persistent amber
banner whenever anything is simulated — so demo data is never visually
indistinguishable from a real deployment. See `docs/GOD_MODE_STATUS.md`
§16 for the full real-vs-simulated inventory.

## Stopping

```bash
kill $(cat .demo_mode.pids)   # backend
# dashboard dev server: Ctrl+C in its terminal, or find/kill its port manually
```

Delete `backend/demo_mode.db` to reset the demo data completely.
