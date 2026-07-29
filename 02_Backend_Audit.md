# 02 Backend Audit

## Scope reviewed
The backend audit was grounded in [backend/app/main.py](backend/app/main.py), [backend/app/config.py](backend/app/config.py), [backend/app/database.py](backend/app/database.py), [backend/app/core/security.py](backend/app/core/security.py), [backend/app/core/deps.py](backend/app/core/deps.py), [backend/app/routers](backend/app/routers), [backend/app/services](backend/app/services), [backend/requirements.txt](backend/requirements.txt), and [backend/tests](backend/tests).

## Architecture assessment
- The application is organized into routers, services, schemas, and models, which is a good foundation.
- The app entrypoint in [backend/app/main.py](backend/app/main.py) wires many routers and creates tables eagerly on startup.
- The design is modular enough for incremental growth, but it is still a monolith rather than a distributed or domain-driven platform.

## Strengths
- FastAPI + SQLAlchemy is a strong match for this product.
- Auth and role checks are explicit in [backend/app/core/deps.py](backend/app/core/deps.py).
- The SOS path is designed to be robust and idempotent.
- Safety evaluation is deterministic and separated from AI explanation in [backend/app/services/safety_engine.py](backend/app/services/safety_engine.py).

## Issues found
- [backend/app/main.py](backend/app/main.py) calls schema creation directly at startup; this is acceptable for development but not a production migration strategy.
- [backend/app/config.py](backend/app/config.py) uses an insecure default JWT secret and weak default values for deployment-sensitive settings.
- [backend/app/core/rate_limit.py](backend/app/core/rate_limit.py) is in-memory and single-process; it is not suitable for a multi-instance deployment.
- [backend/app/services/notification_service.py](backend/app/services/notification_service.py) contains a real provider stub that raises `NotImplementedError` for SMS.
- [backend/app/services/ai/provider.py](backend/app/services/ai/provider.py) relies on template-based explanation when real AI is unavailable, which is acceptable for resilience but not yet production-grade AI.

## API and service quality
- Core routes are present for auth, location, SOS, weather, family, trips, admin, and V2 intelligence flows.
- The system appears consistent in its naming and layering, though some endpoints still use simple dictionaries rather than richer Pydantic validation.

## Backend verdict
- Backend readiness: approximately 82%.
- Status: strong MVP foundation, but needs migration tooling, production secret handling, and more operational hardening before public deployment.
