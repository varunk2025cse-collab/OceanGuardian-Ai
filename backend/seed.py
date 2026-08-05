"""
OceanGuardian AI — Phase 2 seed script.

Run after alembic upgrade head:  python seed.py

Seeds:
  - Weather alerts
  - Market prices
  - Government schemes
  - Tamil Nadu coastal harbors (for offline navigation)
  - A demo operator account — ONLY when SEED_DEMO_DATA=true is set.

Security note (docs/SECURITY.md): earlier versions of this script created
a demo operator account (+911234567890 / rescue123) unconditionally, and
the Dockerfile ran this script on every container start — including
production. That meant every deployment using the stock image had a
well-known operator login live unless someone remembered to delete it.
The demo account is now gated behind SEED_DEMO_DATA, which the production
docker-compose.yml defaults to "false". Set it to "true" only for local
dev/demo environments.
"""
import sys, os
from datetime import date, datetime, timedelta, timezone

SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "false").lower() in ("1", "true", "yes")

# Allow running without a .env (uses DATABASE_URL env var or the default test DB)
from app.database import Base, engine, SessionLocal
from app.core.security import hash_password
# ALL models must be imported so SQLAlchemy can resolve string-based relationships
from app.models.user import User, UserRole
from app.models.location import LocationPing        # noqa: F401 — needed for User.locations rel
from app.models.sos import SOSAlert                 # noqa: F401 — needed for User.sos_alerts rel
from app.models.family_link import FamilyLink       # noqa: F401
from app.models.boat import Boat                    # noqa: F401 — needed for User.boats rel
from app.models.trip import Trip                    # noqa: F401 — needed for User.trips rel
from app.models.weather_alert import WeatherAlert, HazardSeverity, HazardType
from app.models.market_price import MarketPrice
from app.models.govt_scheme import GovtScheme
from app.models.harbor import Harbor

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # ── Demo operator account (dev/demo only — see module docstring) ───────────
    if SEED_DEMO_DATA:
        if not db.query(User).filter(User.phone_number == "+911234567890").first():
            db.add(User(
                phone_number="+911234567890",
                password_hash=hash_password("rescue123"),
                full_name="Rescue Coordinator (DEMO)",
                role=UserRole.operator,
                preferred_language="en",
            ))
            print("SEED_DEMO_DATA=true: created demo operator account  +911234567890 / rescue123")
    else:
        print("SEED_DEMO_DATA not set — skipping demo operator account (production-safe default).")

    # ── Weather alerts ────────────────────────────────────────────────────────
    if db.query(WeatherAlert).count() == 0:
        now = datetime.now(timezone.utc)
        db.add_all([
            WeatherAlert(
                title="High Wave Warning — Tamil Nadu Coast",
                description="Wave heights of 2.5–3.5m expected along the coast. Small craft must NOT venture out to sea.",
                hazard_type=HazardType.high_waves, severity=HazardSeverity.warning,
                center_latitude=11.0, center_longitude=80.0, radius_km=120,
                valid_from=now, valid_until=now + timedelta(days=2), source="INCOIS",
            ),
            WeatherAlert(
                title="Strong Wind Advisory",
                description="Winds of 35–45 km/h likely along and off the coast. Exercise caution.",
                hazard_type=HazardType.strong_wind, severity=HazardSeverity.advisory,
                center_latitude=11.38, center_longitude=79.83, radius_km=80,
                valid_from=now, valid_until=now + timedelta(days=1), source="IMD",
            ),
        ])

    # ── Market prices ─────────────────────────────────────────────────────────
    if db.query(MarketPrice).count() == 0:
        today = date.today()
        db.add_all([
            MarketPrice(species="Seer Fish (Vanjaram)",   market_name="Nagapattinam Fish Market", harbor_region="Nagapattinam", price_per_kg=650, price_date=today),
            MarketPrice(species="Pomfret (Vella Vavval)", market_name="Nagapattinam Fish Market", harbor_region="Nagapattinam", price_per_kg=520, price_date=today),
            MarketPrice(species="Tuna",                   market_name="Cuddalore Harbour Market", harbor_region="Cuddalore",    price_per_kg=280, price_date=today),
            MarketPrice(species="Prawns",                 market_name="Cuddalore Harbour Market", harbor_region="Cuddalore",    price_per_kg=480, price_date=today),
            MarketPrice(species="Mackerel (Ayala)",       market_name="Chennai Kasimedu Market",  harbor_region="Chennai",      price_per_kg=180, price_date=today),
            MarketPrice(species="Red Snapper (Sankara)",  market_name="Rameswaram Fish Market",  harbor_region="Rameswaram",   price_per_kg=420, price_date=today),
        ])

    # ── Government schemes ────────────────────────────────────────────────────
    if db.query(GovtScheme).count() == 0:
        db.add_all([
            GovtScheme(title="PM Matsya Sampada Yojana (PMMSY)", category="subsidy", region="National",
                        description="Central scheme for fisheries development covering infrastructure, boats, and gear.",
                        eligibility="Registered fishermen and fisheries cooperatives.",
                        how_to_apply="Apply through the State Fisheries Department office or the National Fisheries portal.",
                        contact_info="Contact your nearest Fisheries Department office."),
            GovtScheme(title="Group Accident Insurance for Fishermen", category="insurance", region="Tamil Nadu",
                        description="Accident cover for active fishermen including disability and death benefits.",
                        eligibility="Fishermen registered with the State Fisheries Department.",
                        how_to_apply="Enroll via the local Fisheries Department office or cooperative society.",
                        contact_info="Tamil Nadu Fisheries Department helpline."),
            GovtScheme(title="Saving-cum-Relief Scheme", category="relief", region="Tamil Nadu",
                        description="Monthly savings matched by Government for support during the fishing-ban period.",
                        eligibility="Active marine fishermen contributing to the savings scheme.",
                        how_to_apply="Register through the local fishing cooperative society before the fishing season.",
                        contact_info="Local Fisheries Cooperative Society office."),
        ])

    # ── Tamil Nadu coastal harbors ────────────────────────────────────────────
    if db.query(Harbor).count() == 0:
        db.add_all([
            Harbor(name="Chennai Fishing Harbour (Kasimedu)", region="Chennai",    state="Tamil Nadu", latitude=13.1198, longitude=80.3066, contact_phone="044-25940180"),
            Harbor(name="Cuddalore Fishing Harbour",          region="Cuddalore",  state="Tamil Nadu", latitude=11.7647, longitude=79.7680, contact_phone="04142-234567"),
            Harbor(name="Nagapattinam Fishing Harbour",       region="Nagapattinam",state="Tamil Nadu",latitude=10.7660, longitude=79.8440, contact_phone="04365-242700"),
            Harbor(name="Rameswaram Fishing Harbour",         region="Rameswaram", state="Tamil Nadu", latitude=9.2885,  longitude=79.3129, contact_phone="04573-221234"),
            Harbor(name="Thoothukudi (Tuticorin) Harbour",   region="Thoothukudi",state="Tamil Nadu", latitude=8.7975,  longitude=78.1691, contact_phone="0461-2340234"),
            Harbor(name="Kanyakumari Fishing Harbour",        region="Kanyakumari",state="Tamil Nadu", latitude=8.0836,  longitude=77.5546, contact_phone="04652-246891"),
            Harbor(name="Mandapam Fishing Harbour",           region="Ramanathapuram",state="Tamil Nadu",latitude=9.2712, longitude=79.1224),
            Harbor(name="Puducherry Fishing Harbour",         region="Puducherry", state="Puducherry", latitude=11.9254, longitude=79.8380, contact_phone="0413-2336777"),
            Harbor(name="Karaikal Fishing Harbour",           region="Karaikal",   state="Puducherry", latitude=10.9238, longitude=79.8360),
            Harbor(name="Pazhayar Fishing Harbour",           region="Nagapattinam",state="Tamil Nadu",latitude=10.8553, longitude=79.8438),
        ])
        print("Seeded 10 Tamil Nadu coastal harbors")

    try:
        db.commit()
        print("Seed complete.")
    except Exception as e:
        # Be conservative in CI/test environments — log and rollback on IntegrityError
        from sqlalchemy.exc import IntegrityError
        if isinstance(e, IntegrityError):
            print("Seed commit encountered IntegrityError — rolling back. This may be due to repeated seed runs in tests.")
            db.rollback()
        else:
            # Re-raise non-Integrity errors to avoid hiding real problems
            raise

finally:
    db.close()
