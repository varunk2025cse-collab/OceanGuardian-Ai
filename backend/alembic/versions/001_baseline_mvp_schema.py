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
        # On SQLite (tests / local dev) create the baseline tables with
        # op.create_table so that `alembic upgrade head` works from scratch.
        # PostgreSQL uses raw SQL below to avoid SQLAlchemy Enum auto-create bugs.
        if not _table_exists("users"):
            op.create_table(
                "users",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("phone_number", sa.String(20), nullable=False, unique=True),
                sa.Column("password_hash", sa.String(255), nullable=False),
                sa.Column("full_name", sa.String(120), nullable=False),
                sa.Column("role", sa.String(20), nullable=False, server_default="fisherman"),
                sa.Column("boat_name", sa.String(120)),
                sa.Column("boat_registration_number", sa.String(60)),
                sa.Column("home_harbor", sa.String(120)),
                sa.Column("preferred_language", sa.String(10), nullable=False, server_default="ta"),
                sa.Column("emergency_contact_name", sa.String(120)),
                sa.Column("emergency_contact_phone", sa.String(20)),
                sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            )
            op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)

        if not _table_exists("location_pings"):
            op.create_table(
                "location_pings",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("client_uuid", sa.String(36), nullable=False, unique=True),
                sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
                sa.Column("latitude", sa.Float, nullable=False),
                sa.Column("longitude", sa.Float, nullable=False),
                sa.Column("accuracy_meters", sa.Float),
                sa.Column("speed_mps", sa.Float),
                sa.Column("heading_degrees", sa.Float),
                sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )
            op.create_index("ix_location_pings_user_id", "location_pings", ["user_id"])
            op.create_index("ix_location_pings_client_uuid", "location_pings", ["client_uuid"], unique=True)

        if not _table_exists("sos_alerts"):
            op.create_table(
                "sos_alerts",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("client_uuid", sa.String(36), nullable=False, unique=True),
                sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
                sa.Column("latitude", sa.Float, nullable=False),
                sa.Column("longitude", sa.Float, nullable=False),
                sa.Column("accuracy_meters", sa.Float),
                sa.Column("battery_level_percent", sa.Integer),
                sa.Column("message", sa.Text),
                sa.Column("status", sa.String(20), nullable=False, server_default="active"),
                sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
                sa.Column("resolved_at", sa.DateTime(timezone=True)),
                sa.Column("resolved_note", sa.Text),
            )
            op.create_index("ix_sos_alerts_user_id", "sos_alerts", ["user_id"])
            op.create_index("ix_sos_alerts_client_uuid", "sos_alerts", ["client_uuid"], unique=True)
            op.create_index("ix_sos_alerts_status", "sos_alerts", ["status"])

        if not _table_exists("family_links"):
            op.create_table(
                "family_links",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("fisherman_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
                sa.Column("family_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
                sa.Column("relation", sa.String(50)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )
            op.create_index("ix_family_links_id", "family_links", ["id"])

        if not _table_exists("weather_alerts"):
            op.create_table(
                "weather_alerts",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("title", sa.String(160), nullable=False),
                sa.Column("description", sa.Text, nullable=False),
                sa.Column("hazard_type", sa.String(50), nullable=False),
                sa.Column("severity", sa.String(20), nullable=False),
                sa.Column("center_latitude", sa.Float, nullable=False),
                sa.Column("center_longitude", sa.Float, nullable=False),
                sa.Column("radius_km", sa.Float, nullable=False, server_default="50"),
                sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
                sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
                sa.Column("source", sa.String(120)),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )
            op.create_index("ix_weather_alerts_severity", "weather_alerts", ["severity"])

        if not _table_exists("market_prices"):
            op.create_table(
                "market_prices",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("species", sa.String(80), nullable=False),
                sa.Column("market_name", sa.String(120), nullable=False),
                sa.Column("harbor_region", sa.String(120), nullable=False),
                sa.Column("price_per_kg", sa.Float, nullable=False),
                sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
                sa.Column("price_date", sa.Date, nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )
            op.create_index("ix_market_prices_price_date", "market_prices", ["price_date"])
            op.create_index("ix_market_prices_harbor_region", "market_prices", ["harbor_region"])
            op.create_index("ix_market_prices_species", "market_prices", ["species"])

        if not _table_exists("govt_schemes"):
            op.create_table(
                "govt_schemes",
                sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("title", sa.String(200), nullable=False),
                sa.Column("category", sa.String(60), nullable=False),
                sa.Column("region", sa.String(120), nullable=False, server_default="National"),
                sa.Column("description", sa.Text, nullable=False),
                sa.Column("eligibility", sa.Text, nullable=False),
                sa.Column("how_to_apply", sa.Text, nullable=False),
                sa.Column("contact_info", sa.String(255)),
                sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            )

        return

    # =================================================================
    # PostgreSQL — raw SQL (immune to SQLAlchemy Enum auto-create bugs)
    # =================================================================

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
