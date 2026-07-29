"""Phase 2 — boats, trips, harbors tables + SOS/location column additions.

Revision ID: 002
Revises: 001
Create Date: 2026-06-21

New tables: boats, harbors, trips
Column additions to existing tables:
  users           : (no column changes — operator role added to userrole enum)
  sos_alerts      : priority, rescue_notes, acknowledged_by, resolved_by
  location_pings  : trip_id (FK to trips.id, nullable)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return sa_inspect(bind).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    if not sa_inspect(bind).has_table(table):
        return False
    cols = [c["name"] for c in sa_inspect(bind).get_columns(table)]
    return column in cols


def _type_exists(name: str) -> bool:
    bind = op.get_bind()
    try:
        result = bind.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": name})
        return result.fetchone() is not None
    except Exception:
        return False  # SQLite — no pg_type


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # ── 1. Add 'operator' value to userrole enum (PostgreSQL only) ────────────
    if not is_sqlite and _type_exists("userrole"):
        # PostgreSQL 12+ allows ALTER TYPE inside a transaction
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'operator'")

    # ── 2. Create boats table ─────────────────────────────────────────────────
    if not _table_exists("boats"):
        op.create_table(
            "boats",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("registration_number", sa.String(60), unique=True),
            sa.Column("color", sa.String(60)),
            sa.Column("length_meters", sa.Float),
            sa.Column("engine_type", sa.String(80)),
            sa.Column("engine_horsepower", sa.Integer),
            sa.Column("fuel_capacity_liters", sa.Float),
            sa.Column("safety_equipment", sa.Text),   # JSON-encoded list
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # ── 3. Create harbors table ───────────────────────────────────────────────
    if not _table_exists("harbors"):
        op.create_table(
            "harbors",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("region", sa.String(120), nullable=False),
            sa.Column("state", sa.String(80), nullable=False, server_default="Tamil Nadu"),
            sa.Column("latitude", sa.Float, nullable=False),
            sa.Column("longitude", sa.Float, nullable=False),
            sa.Column("contact_phone", sa.String(20)),
            sa.Column("description", sa.Text),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # ── 4. Create trips table ─────────────────────────────────────────────────
    if not _table_exists("trips"):
        op.create_table(
            "trips",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("boat_id", sa.Integer, sa.ForeignKey("boats.id")),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("end_time", sa.DateTime(timezone=True)),
            sa.Column("estimated_return_at", sa.DateTime(timezone=True)),
            sa.Column("start_latitude", sa.Float),
            sa.Column("start_longitude", sa.Float),
            sa.Column("destination", sa.String(120)),
            sa.Column("notes", sa.Text),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # ── 5. Add Phase 2 columns to sos_alerts ──────────────────────────────────
    if not _column_exists("sos_alerts", "priority"):
        op.add_column("sos_alerts", sa.Column("priority", sa.String(20), server_default="high"))
    if not _column_exists("sos_alerts", "rescue_notes"):
        op.add_column("sos_alerts", sa.Column("rescue_notes", sa.Text))

    # Columns with FK constraints need batch_alter_table on SQLite
    # (SQLite doesn't support ALTER TABLE ADD CONSTRAINT)
    with op.batch_alter_table("sos_alerts") as batch_op:
        if not _column_exists("sos_alerts", "acknowledged_by"):
            batch_op.add_column(sa.Column("acknowledged_by", sa.Integer))
            batch_op.create_foreign_key("fk_sos_alerts_acknowledged_by", "users", ["acknowledged_by"], ["id"])
        if not _column_exists("sos_alerts", "resolved_by"):
            batch_op.add_column(sa.Column("resolved_by", sa.Integer))
            batch_op.create_foreign_key("fk_sos_alerts_resolved_by", "users", ["resolved_by"], ["id"])

    # ── 6. Add trip_id to location_pings ──────────────────────────────────────
    with op.batch_alter_table("location_pings") as batch_op:
        if not _column_exists("location_pings", "trip_id"):
            batch_op.add_column(sa.Column("trip_id", sa.Integer))
            batch_op.create_foreign_key("fk_location_pings_trip_id", "trips", ["trip_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # Remove trip_id from location_pings
    if _column_exists("location_pings", "trip_id"):
        with op.batch_alter_table("location_pings") as batch_op:
            batch_op.drop_column("trip_id")

    # Remove Phase 2 columns from sos_alerts
    for col in ("resolved_by", "acknowledged_by", "rescue_notes", "priority"):
        if _column_exists("sos_alerts", col):
            with op.batch_alter_table("sos_alerts") as batch_op:
                batch_op.drop_column(col)

    # Drop tables in reverse FK order
    for tbl in ("trips", "harbors", "boats"):
        if _table_exists(tbl):
            op.drop_table(tbl)

    # Note: removing 'operator' from the userrole enum is not supported in PostgreSQL
    # without recreating the type. If you need to roll back the enum, do it manually.
