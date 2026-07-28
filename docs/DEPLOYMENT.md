# Deployment

> Supersedes the root-level `DEPLOYMENT_GUIDE.md` (a Phase 2-era doc with
> stale claims — "35 endpoints," "12/12 tests" — kept for history, not
> authoritative). This document reflects the actual current state.

## Local development (no Docker)

See `README.md` "Manual local development" — backend via `uvicorn`,
dashboard via `npm run dev`, mobile via `flutter run`.

## Docker Compose

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and JWT_SECRET_KEY to real random values
#   openssl rand -hex 24   # for POSTGRES_PASSWORD
#   openssl rand -hex 32   # for JWT_SECRET_KEY

cd rescue-dashboard && npm install && npm run build && cd ..
docker compose up --build
```

`docker-compose.yml` will **refuse to start** if `POSTGRES_PASSWORD` or
`JWT_SECRET_KEY` are unset — this is deliberate (see `docs/SECURITY.md`;
the original version of this file had both hardcoded).

Services:
- `db` — Postgres 16, healthchecked
- `api` — FastAPI backend, runs `alembic upgrade head && seed.py && uvicorn`
  on start. `seed.py` only creates the demo operator account when
  `SEED_DEMO_DATA=true` is explicitly set — leave it unset for a real
  deployment.
- `dashboard` — nginx serving the pre-built React app, reverse-proxies
  `/api/` to the backend (see `nginx.conf`)

## Production checklist

Before deploying anywhere reachable outside your own machine:

- [ ] `JWT_SECRET_KEY` is a real random value (`openssl rand -hex 32`), not the placeholder
- [ ] `POSTGRES_PASSWORD` is a real random value, not `oceanguardian`
- [ ] `CORS_ORIGINS` is an explicit origin list, not `*`
- [ ] `SEED_DEMO_DATA` is unset or `false`
- [ ] `DEMO_MODE` is unset or `false`
- [ ] `ENVIRONMENT` is set to something other than `development`/`test`
      (rate limiting only activates when `ENVIRONMENT != "test"` — see
      `backend/app/core/rate_limit.py`)
- [ ] Decide on `AI_PROVIDER`/`NOTIFICATION_PROVIDER` — the safe defaults
      (template / simulation) are honest and functional, but a real
      deployment protecting real fishermen should have a real
      notification channel configured and verified (see
      `docs/NOTIFICATIONS.md` — this path is implemented but unverified
      in this codebase's own development environment)
- [ ] Run `alembic upgrade head` against the real Postgres database before
      first boot (the app's `create_all()` dev shim is SQLite-only —
      see `docs/CI.md` for why this matters)
- [ ] Review `docs/SECURITY.md`'s "Known limitations" section

## Database migrations

```bash
# Fresh Postgres deployment:
alembic upgrade head        # runs the full migration chain (001 → 008)

# After adding a new model/column:
alembic revision --autogenerate -m "description"
alembic upgrade head
```

CI (`docs/CI.md`) runs `alembic upgrade head` against a real ephemeral
Postgres container on every push — a broken migration is caught before
merge, not at deploy time.

## Mobile app distribution

Not yet set up — `mobile/` has no `android/`/`ios/` platform folders
committed (matches the state documented in `docs/V1_AUDIT.md`; this is a
real product decision, not an oversight). Before building a distributable
binary:

```bash
cd mobile
flutter create .              # generates android/ and ios/ folders
flutter build apk --dart-define=OG_API_BASE_URL=https://your-api.example
# or: flutter build ios ...
```
