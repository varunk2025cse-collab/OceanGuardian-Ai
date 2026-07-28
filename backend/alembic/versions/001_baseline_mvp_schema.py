"""Baseline — MVP schema (raw SQL, immune to SQLAlchemy Enum auto-create bugs).

Revision ID: 001
Revises: (none)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect, text

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(name):
    return sa_inspect(op.get_bind()).has_table(name)


def _pg_exec(sql):
    op.execute(text(sql))


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # Tests use create_all() in test setup; 001 is a no-op for SQLite.
        return

    # Enum types — DO/EXCEPTION pattern is the idiomatic "CREATE IF NOT EXISTS" for PG enums
    _pg_exec("""DO $$ BEGIN CREATE TYPE userrole AS ENUM ('fisherman','family','operator');
                EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _pg_exec("""DO $$ BEGIN CREATE TYPE sosstatus AS ENUM ('active','acknowledged','resolved','false_alarm');
                EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _pg_exec("""DO $$ BEGIN CREATE TYPE hazardseverity AS ENUM ('advisory','warning','danger');
                EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
    _pg_exec("""DO $$ BEGIN CREATE TYPE hazardtype AS ENUM ('cyclone','high_waves','storm','strong_wind','lightning');
                EXCEPTION WHEN duplicate_object THEN NULL; END $$""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        phone_number VARCHAR(20) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(120) NOT NULL,
        role userrole NOT NULL DEFAULT 'fisherman',
        boat_name VARCHAR(120),
        boat_registration_number VARCHAR(60),
        home_harbor VARCHAR(120),
        preferred_language VARCHAR(10) NOT NULL DEFAULT 'ta',
        emergency_contact_name VARCHAR(120),
        emergency_contact_phone VARCHAR(20),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS location_pings (
        id SERIAL PRIMARY KEY,
        client_uuid VARCHAR(36) NOT NULL UNIQUE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        accuracy_meters FLOAT,
        speed_mps FLOAT,
        heading_degrees FLOAT,
        recorded_at TIMESTAMPTZ NOT NULL,
        synced_at TIMESTAMPTZ DEFAULT NOW()
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS sos_alerts (
        id SERIAL PRIMARY KEY,
        client_uuid VARCHAR(36) NOT NULL UNIQUE,
        user_id INTEGER NOT NULL REFERENCES users(id),
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        accuracy_meters FLOAT,
        battery_level_percent INTEGER,
        message TEXT,
        status sosstatus NOT NULL DEFAULT 'active',
        triggered_at TIMESTAMPTZ NOT NULL,
        received_at TIMESTAMPTZ DEFAULT NOW(),
        resolved_at TIMESTAMPTZ,
        resolved_note TEXT
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS family_links (
        id SERIAL PRIMARY KEY,
        fisherman_id INTEGER NOT NULL REFERENCES users(id),
        family_user_id INTEGER NOT NULL REFERENCES users(id),
        relation VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT uq_family_link_pair UNIQUE (fisherman_id, family_user_id)
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS weather_alerts (
        id SERIAL PRIMARY KEY,
        title VARCHAR(160) NOT NULL,
        description TEXT NOT NULL,
        hazard_type hazardtype NOT NULL,
        severity hazardseverity NOT NULL,
        center_latitude FLOAT NOT NULL,
        center_longitude FLOAT NOT NULL,
        radius_km FLOAT NOT NULL DEFAULT 50,
        valid_from TIMESTAMPTZ NOT NULL,
        valid_until TIMESTAMPTZ NOT NULL,
        source VARCHAR(120),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS market_prices (
        id SERIAL PRIMARY KEY,
        species VARCHAR(80) NOT NULL,
        market_name VARCHAR(120) NOT NULL,
        harbor_region VARCHAR(120) NOT NULL,
        price_per_kg FLOAT NOT NULL,
        currency VARCHAR(8) NOT NULL DEFAULT 'INR',
        price_date DATE NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")

    _pg_exec("""CREATE TABLE IF NOT EXISTS govt_schemes (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        category VARCHAR(60) NOT NULL,
        region VARCHAR(120) NOT NULL DEFAULT 'National',
        description TEXT NOT NULL,
        eligibility TEXT NOT NULL,
        how_to_apply TEXT NOT NULL,
        contact_info VARCHAR(255),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")


def downgrade():
    raise NotImplementedError("Downgrade of baseline is not supported.")
