# Security

Consolidates the audit findings (`docs/V1_AUDIT.md` §10) and the V2 core
build's Phase 21 hardening pass. Status per item below.

## Fixed

| Issue | Fix | Where |
|---|---|---|
| Unauthenticated privilege escalation — anyone could self-register as `operator` | `role` pattern restricted to `fisherman\|family`; defense-in-depth 403 in the router even if the schema constraint is ever loosened | `backend/app/schemas/user.py`, `backend/app/routers/auth.py` (Phase 0 hotfix) |
| Hardcoded demo operator account (`+911234567890`/`rescue123`) auto-seeded on every Docker container start, including production | Gated behind `SEED_DEMO_DATA=true`, defaults to `false` | `backend/seed.py` |
| Hardcoded weak Postgres/JWT secrets committed in `docker-compose.yml` | Replaced with required env var substitution (`${VAR:?error if unset}`); root `.env.example` added | `docker-compose.yml`, `.env.example` |
| No rate limiting on auth endpoints | In-memory sliding-window limiter on `/auth/login` (20/min) and `/auth/register` (10/min) | `backend/app/core/rate_limit.py` |
| Docker container ran as root, no healthcheck | Non-root user, `HEALTHCHECK` against `/health` | `backend/Dockerfile` |
| Mobile session tokens in plaintext `shared_preferences` | Moved to `flutter_secure_storage` (Keystore/Keychain-backed) | `mobile/lib/services/auth_service.dart` |
| Dashboard shipped pre-filled demo credentials in the login form | Removed | `rescue-dashboard/src/pages/LoginPagePremium.jsx` |
| 5 orphaned/dead dashboard page files | Deleted (confirmed unreferenced by `App.jsx` first) | `rescue-dashboard/src/pages/` |

## Deliberately NOT rate-limited

`POST /api/v1/sos/trigger` is exempt by design. A fisherman's retry storm
during a real emergency is exactly the traffic this system exists to
accept — throttling it would directly contradict the safety-first
principle. See `backend/app/core/rate_limit.py` docstring.

## Known limitations (not fixed this pass — documented, not hidden)

- **Rate limiter is single-process, in-memory.** A multi-worker or
  multi-instance deployment would enforce the limit independently per
  process, not cluster-wide. Cluster-safe rate limiting is available via
  `RATE_LIMIT_BACKEND=redis` and `REDIS_URL` once the optional `redis`
  package is installed. The code now allows this configuration and
  falls back safely to in-memory mode when Redis is unavailable.
- **`python-jose`** (JWT library) is still in use — a lower-maintenance-
  velocity dependency than alternatives like `PyJWT`. `PyJWT>=2.8.0` is
  now added to `requirements.txt` as the supported migration target. The
  migration path is documented in `backend/app/core/security.py`.
- **Dependency vulnerability scanning is now surfaced in CI.** The
  backend CI job installs `pip-audit` and runs it against
  `requirements.txt`, continuing on error so the existing `python-jose`
  advisory is visible without blocking the build.
- **CORS still defaults to `*`** in `.env.example` for local-dev
  convenience. Explicitly documented as unsafe for any shared/staging/
  production deployment; `docker-compose.yml` already overrides it to an
  explicit origin list.
- **`python-jose`** (JWT library) is still in use — a lower-maintenance-
  velocity dependency than alternatives like `PyJWT`. Flagged in the
  original audit, not swapped this pass (would be a larger, higher-risk
  change for a working auth path with no specific known CVE driving it).
- **No dependency vulnerability scanning** (`pip-audit`/`safety`/
  Dependabot) configured yet.
- **AnthropicProvider and TwilioSmsProvider are implemented against their
  documented API contracts but not runtime-verified** — no credentials
  exist in this environment. See `docs/AI_ARCHITECTURE.md` and
  `docs/NOTIFICATIONS.md`.

## Location Privacy

Enforced consistently across every new endpoint added this pass, matching
the existing V1 pattern:
- **Fisherman**: own data only.
- **Family**: only a fisherman they are explicitly linked to
  (`FamilyLink` table) — checked identically in `tracking_service`,
  `safety_engine` router, `incident_service.authorize_view`, and the AI
  tool layer.
- **Operator**: full access (role-gated via `get_current_operator`).

No new endpoint in this pass introduces a path to another fisherman's
location, safety state, or incidents without one of the above checks.
