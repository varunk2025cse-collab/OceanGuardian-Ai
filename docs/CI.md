# Continuous Integration

`.github/workflows/ci.yml` — runs on every push to `main` and every pull
request targeting `main`.

## Jobs

| Job | What it does | Fails the build on |
|---|---|---|
| `backend` | Installs deps, runs `alembic upgrade head` against a real `postgres:16-alpine` service container, then the full pytest suite (212 tests) against SQLite | Any migration error, any test failure |
| `mobile` | `flutter pub get`, `flutter gen-l10n`, `flutter analyze --no-fatal-infos --fatal-warnings`, `flutter test` | Any analyzer error/warning, any test failure |
| `dashboard` | `npm install`, `npm run build` | Any build error |
| `secret-scan` | `gitleaks` over the full history | Any detected secret pattern |

## Why a real Postgres migration check

`backend/app/main.py` uses `Base.metadata.create_all()` as a dev-ergonomics
shim on SQLite — which means running the test suite locally (SQLite)
never actually exercises the Alembic migration chain the way a real
Postgres deployment would. The CI `backend` job spins up a real Postgres
service container specifically to run `alembic upgrade head` against it,
so a broken migration is caught before merge, not at deploy time.

## Honesty note on local verification

This CI configuration was written and reviewed against GitHub Actions'
documented service-container pattern (a standard, widely-used setup) but
**has not been dry-run against a live GitHub Actions run in this session**
— there is no GitHub remote configured for this repository yet (see
`docs/DEPLOYMENT.md`). The individual commands it runs
(`pip install`, `alembic upgrade head`, `pytest`, `flutter analyze`,
`flutter test`, `npm run build`) have all been run and verified locally
in this session; what's unverified is specifically the GitHub Actions
orchestration layer around them (service container networking, action
versions). Recommended first step after pushing to GitHub: watch the
first `ci.yml` run closely and fix anything environment-specific that
surfaces.

## What's intentionally NOT in CI yet

- **Mobile build for a real device/emulator** (`flutter build apk`/`ios`)
  — the project has no `android/`/`ios/` platform folders yet (matches
  the pre-existing state documented in `docs/V1_AUDIT.md`; `flutter
  create .` needs to be run first, a real product decision, not a CI gap).
- **Dashboard tests** — no test framework exists yet (`docs/V1_AUDIT.md`
  §7). `npm run build` is still a meaningful smoke test.
- **Dependency vulnerability scanning** (`pip-audit`, `npm audit` as a
  hard gate) — flagged as a known gap in `docs/SECURITY.md`, not added
  here to avoid introducing a new class of CI flakiness (transitive
  vulnerability databases change daily) without first triaging existing
  findings, which needs a human decision, not an automatic block.
