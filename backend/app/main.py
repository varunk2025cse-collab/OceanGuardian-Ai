"""
OceanGuardian AI — Phase 5 backend entrypoint.

Run (dev):        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Run (production): alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000

Schema management:
  - Development / fresh SQLite installs : create_all() below handles it automatically.
  - Production PostgreSQL upgrades       : always run `alembic upgrade head` first.
    create_all() is intentionally kept for developer ergonomics — it is a no-op on
    tables that already exist, and idempotent on columns it didn't create (Phase 2
    column additions to existing tables need `alembic upgrade head`).

Includes Phase 5 Intelligence Layer:
  - Harbor Intelligence API (v2)
  - Fuel & Boat Health System (v2)
  - Smart Check-in System (v2)
  - Risk Prediction Engine (v2)
  - AI Marine Copilot (v2)
  - Family Safety Portal (v2)
  - Analytics Engine (v2)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, SessionLocal, ensure_compatible_schema
from app.logging_config import logger

# ── Import every model module so they register on Base.metadata ──────────────
# This ensures create_all() below and Alembic autogenerate both see the full schema.
from app.models import user, family_link, location, sos        # noqa: F401
from app.models import weather_alert, market_price, govt_scheme  # noqa: F401
from app.models import boat, trip                                    # noqa: F401 Phase 2, 009
from app.models import phase5                                    # noqa: F401 Phase 5

# ── Create tables (dev ergonomics) ────────────────────────────────────────────
# Safe on existing databases (no-op for tables that already exist).
# For column additions to existing tables in a running deployment, run:
#   alembic upgrade head
logger.info(f"Starting OceanGuardian AI - Environment: {settings.environment}")
Base.metadata.create_all(bind=engine)
ensure_compatible_schema(engine)
logger.info("Database tables initialized")

# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers import auth, location as loc_router, sos as sos_router   # noqa: E402
from app.routers import weather, market, schemes, family                   # noqa: E402
from app.routers import boats, trips, harbors, risk, admin                 # noqa: E402
from app.routers import admin_users                                         # noqa: E402

# Phase 5 v2 API routes
from app.routers.v2 import harbor as harbor_v2                             # noqa: E402
from app.routers.v2 import boat_health as boat_health_v2                   # noqa: E402
from app.routers.v2 import family_portal as family_portal_v2               # noqa: E402
from app.routers.v2 import analytics as analytics_v2                       # noqa: E402
from app.routers.v2 import checkin as checkin_v2                           # noqa: E402
from app.routers.v2 import risk_prediction as risk_prediction_v2           # noqa: E402
from app.routers.v2 import escalation as escalation_v2                     # noqa: E402
from app.routers.v2 import tracking as tracking_v2                         # noqa: E402
from app.routers.v2 import safety as safety_v2                             # noqa: E402
from app.routers.v2 import boats as boats_v2                               # noqa: E402
from app.routers.v2 import weather as weather_v2                           # noqa: E402
from app.routers.v2 import incidents as incidents_v2                       # noqa: E402
from app.routers.v2 import ai as ai_v2                                     # noqa: E402
from app.routers.v2 import boat_equipment_inspections as equip_insp_v2      # noqa: E402
from app.routers.v2 import intelligence as intelligence_v2                 # noqa: E402

app = FastAPI(
    title=settings.app_name,
    description=(
        "OceanGuardian AI – Phase 5: AI Intelligence Layer with Harbor Intelligence, "
        "Fuel & Boat Health Tracking, Smart Risk Prediction, Smart Check-in System, "
        "AI Marine Copilot, Advanced Family Safety Portal, and Analytics Engine. "
        "Builds on Phase 1-4 foundation (offline GPS, SOS, weather risk, boats, trips, "
        "family tracking, and React Rescue Dashboard)."
    ),
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fisherman-facing (Flutter)
app.include_router(auth.router)
app.include_router(loc_router.router)
app.include_router(sos_router.router)
app.include_router(weather.router)
app.include_router(market.router)
app.include_router(schemes.router)
app.include_router(family.router)
app.include_router(boats.router)
app.include_router(trips.router)
app.include_router(harbors.router)
app.include_router(risk.router)

# Operator-facing (React Rescue Dashboard)
app.include_router(admin.router)
app.include_router(admin_users.router)

# Phase 5 Intelligence Layer v2 APIs
app.include_router(harbor_v2.router)
app.include_router(boat_health_v2.router)
app.include_router(family_portal_v2.router)
app.include_router(analytics_v2.router)
app.include_router(checkin_v2.router)
app.include_router(risk_prediction_v2.router)
app.include_router(escalation_v2.router)
app.include_router(tracking_v2.router)
app.include_router(safety_v2.router)
app.include_router(weather_v2.router)
app.include_router(incidents_v2.router)
app.include_router(ai_v2.router)
app.include_router(boats_v2.router)
app.include_router(equip_insp_v2.router)
app.include_router(intelligence_v2.router)


@app.get("/", tags=["health"])
def root():
    logger.debug("Root endpoint accessed")
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "0.5.0",
        "environment": settings.environment,
    }


@app.get("/health", tags=["health"])
def health():
    """Enhanced health check with database connectivity test."""
    from sqlalchemy import text
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.5.0",
        "environment": settings.environment,
    }


@app.get("/api/v1/system-info", tags=["health"])
def system_info():
    """Unauthenticated, non-sensitive provider/mode status — lets the
    mobile app and rescue dashboard render an honest "DEMO / SIMULATION
    MODE" banner and show which integrations are real vs. simulated,
    rather than letting that be invisible to the end user. Never exposes
    secret values, only which mode each provider is in."""
    return {
        "demo_mode": settings.demo_mode,
        "environment": settings.environment,
        "weather_provider": settings.weather_provider,
        "ai_provider": settings.ai_provider if settings.ai_provider == "template" else (
            "anthropic" if settings.anthropic_api_key else "template (ANTHROPIC_API_KEY not set — falling back)"
        ),
        "notification_provider": settings.notification_provider if settings.notification_provider == "simulation" else (
            "twilio" if (settings.twilio_account_sid and settings.twilio_auth_token) else "simulation (Twilio credentials not set — falling back)"
        ),
    }
