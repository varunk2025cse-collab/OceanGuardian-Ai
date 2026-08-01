"""Boat Management Enterprise — migration 009.

Extends the existing `boats` table with status, vessel classification,
engine detail, soft-delete, optimistic locking, verification, and QR
columns.  Adds 7 new tables for the full boat management lifecycle:
  boat_documents, boat_crew_members, boat_inspections,
  boat_equipment_items, boat_status_history, boat_audit_logs,
  boat_ownership_transfers.

Also patches three existing Phase-5 health tables with missing columns:
  boat_maintenance  → status, completed_by, updated_at
  boat_health_status → unique constraint on boat_id
  boat_fuel_logs    → logged_by

All changes are additive / nullable / server-defaulted so existing rows
remain valid on both SQLite (tests) and PostgreSQL (production).

Revision ID: 009_boat_management_enterprise
Revises: 008_safety_incident_engine
Create Date: 2025-01-03 00:00:00.000000
"""
from alembic import op 
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "009_boat_management_enterprise"
down_revision = "008_safety_incident_engine"
branch_labels = None
depends_on = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa_inspect(bind).get_columns(table)}


def _table_exists(name: str) -> bool:
    return sa_inspect(op.get_bind()).has_table(name)


def _index_exists(name: str, table: str) -> bool:
    bind = op.get_bind()
    return any(
        ix["name"] == name
        for ix in sa_inspect(bind).get_indexes(table)
    )


def _unique_exists(table: str, column: str) -> bool:
    """Return True if any unique constraint covers exactly this single column."""
    bind = op.get_bind()
    for uc in sa_inspect(bind).get_unique_constraints(table):
        if uc.get("column_names") == [column]:
            return True
    return False


# ── upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # ── 1. Extend boats table ─────────────────────────────────────────────────
    boats_new_cols = [
        ("status",               sa.String(30),  {"server_default": "active",      "nullable": False}),
        ("vessel_class",         sa.String(50),  {"nullable": True}),
        ("hull_material",        sa.String(50),  {"nullable": True}),
        ("beam_meters",          sa.Float(),     {"nullable": True}),
        ("draft_meters",         sa.Float(),     {"nullable": True}),
        ("year_built",           sa.Integer(),   {"nullable": True}),
        ("engine_make",          sa.String(80),  {"nullable": True}),
        ("engine_model",         sa.String(80),  {"nullable": True}),
        ("engine_serial_number", sa.String(80),  {"nullable": True}),
        ("engine_year",          sa.Integer(),   {"nullable": True}),
        ("home_harbor_id",       sa.Integer(),   {"nullable": True}),
        ("verification_status",  sa.String(30),  {"server_default": "unverified",  "nullable": False}),
        ("verified_by",          sa.Integer(),   {"nullable": True}),
        ("verified_at",          sa.DateTime(),  {"nullable": True}),
        ("qr_code_token",        sa.String(255), {"nullable": True}),
        ("photo_urls",           sa.Text(),      {"nullable": True}),
        ("deleted_at",           sa.DateTime(),  {"nullable": True}),
        ("version",              sa.Integer(),   {"server_default": "1",           "nullable": False}),
        ("created_by",           sa.Integer(),   {"nullable": True}),
        ("updated_by",           sa.Integer(),   {"nullable": True}),
    ]
    for col_name, col_type, kwargs in boats_new_cols:
        if not _col_exists("boats", col_name):
            op.add_column("boats", sa.Column(col_name, col_type, **kwargs))

    # Indexes on boats (guard each with existence check)
    if not _index_exists("ix_boats_status", "boats"):
        op.create_index("ix_boats_status", "boats", ["status"])
    if not _index_exists("ix_boats_home_harbor_id", "boats"):
        op.create_index("ix_boats_home_harbor_id", "boats", ["home_harbor_id"])
    if not _index_exists("ix_boats_verification_status", "boats"):
        op.create_index("ix_boats_verification_status", "boats", ["verification_status"])
    if not _index_exists("ix_boats_deleted_at", "boats"):
        op.create_index("ix_boats_deleted_at", "boats", ["deleted_at"])

    # ── 2. boat_documents ─────────────────────────────────────────────────────
    if not _table_exists("boat_documents"):
        op.create_table(
            "boat_documents",
            sa.Column("id",                sa.Integer(),     primary_key=True),
            sa.Column("boat_id",           sa.Integer(),     sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_type",     sa.String(50),    nullable=False),
            sa.Column("document_number",   sa.String(120),   nullable=True),
            sa.Column("issuing_authority", sa.String(120),   nullable=True),
            sa.Column("issue_date",        sa.Date(),        nullable=True),
            sa.Column("expiry_date",       sa.Date(),        nullable=True),
            sa.Column("file_url",          sa.String(500),   nullable=True),
            sa.Column("file_hash",         sa.String(64),    nullable=True),   # SHA-256
            sa.Column("is_verified",       sa.Boolean(),     nullable=False, server_default="false"),
            sa.Column("verified_by",       sa.Integer(),     sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("verified_at",       sa.DateTime(),    nullable=True),
            sa.Column("notes",             sa.Text(),        nullable=True),
            sa.Column("deleted_at",        sa.DateTime(),    nullable=True),
            sa.Column("created_at",        sa.DateTime(),    nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",        sa.DateTime(),    nullable=False, server_default=sa.func.now()),
            sa.Column("created_by",        sa.Integer(),     sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by",        sa.Integer(),     sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_boat_documents_boat_id",   "boat_documents", ["boat_id"])
        op.create_index("ix_boat_documents_type",      "boat_documents", ["document_type"])
        op.create_index("ix_boat_documents_expiry",    "boat_documents", ["expiry_date"])

    # ── 3. boat_crew_members ──────────────────────────────────────────────────
    if not _table_exists("boat_crew_members"):
        op.create_table(
            "boat_crew_members",
            sa.Column("id",                 sa.Integer(),  primary_key=True),
            sa.Column("boat_id",            sa.Integer(),  sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id",            sa.Integer(),  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("full_name",          sa.String(120), nullable=False),
            sa.Column("phone_number",       sa.String(20),  nullable=True),
            sa.Column("aadhaar_last4",      sa.String(4),   nullable=True),
            sa.Column("role",               sa.String(50),  nullable=False),
            sa.Column("is_primary_contact", sa.Boolean(),   nullable=False, server_default="false"),
            sa.Column("is_active",          sa.Boolean(),   nullable=False, server_default="true"),
            sa.Column("assigned_at",        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("removed_at",         sa.DateTime(),  nullable=True),
            sa.Column("removal_reason",     sa.Text(),      nullable=True),
            sa.Column("created_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",         sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("created_by",         sa.Integer(),   sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_crew_boat_id",  "boat_crew_members", ["boat_id"])
        op.create_index("ix_crew_user_id",  "boat_crew_members", ["user_id"])
        op.create_index("ix_crew_active",   "boat_crew_members", ["boat_id", "is_active"])

    # ── 4. boat_inspections ───────────────────────────────────────────────────
    if not _table_exists("boat_inspections"):
        op.create_table(
            "boat_inspections",
            sa.Column("id",                   sa.Integer(),    primary_key=True),
            sa.Column("boat_id",              sa.Integer(),    sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("inspection_type",      sa.String(50),   nullable=False),
            sa.Column("inspector_name",       sa.String(120),  nullable=True),
            sa.Column("inspector_authority",  sa.String(120),  nullable=True),
            sa.Column("inspection_date",      sa.Date(),       nullable=False),
            sa.Column("next_due_date",        sa.Date(),       nullable=True),
            sa.Column("result",               sa.String(20),   nullable=False),
            sa.Column("findings",             sa.Text(),       nullable=True),
            sa.Column("corrective_actions",   sa.Text(),       nullable=True),
            sa.Column("certificate_number",   sa.String(80),   nullable=True),
            sa.Column("certificate_url",      sa.String(500),  nullable=True),
            sa.Column("deleted_at",           sa.DateTime(),   nullable=True),
            sa.Column("created_at",           sa.DateTime(),   nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",           sa.DateTime(),   nullable=False, server_default=sa.func.now()),
            sa.Column("created_by",           sa.Integer(),    sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_inspections_boat_id", "boat_inspections", ["boat_id"])
        op.create_index("ix_inspections_date",    "boat_inspections", ["inspection_date"])
        op.create_index("ix_inspections_result",  "boat_inspections", ["result"])

    # ── 5. boat_equipment_items ───────────────────────────────────────────────
    if not _table_exists("boat_equipment_items"):
        op.create_table(
            "boat_equipment_items",
            sa.Column("id",              sa.Integer(),   primary_key=True),
            sa.Column("boat_id",         sa.Integer(),   sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category",        sa.String(50),  nullable=False),
            sa.Column("item_name",       sa.String(120), nullable=False),
            sa.Column("quantity",        sa.Integer(),   nullable=False, server_default="1"),
            sa.Column("condition",       sa.String(20),  nullable=False, server_default="good"),
            sa.Column("last_checked_at", sa.Date(),      nullable=True),
            sa.Column("expiry_date",     sa.Date(),      nullable=True),
            sa.Column("notes",           sa.Text(),      nullable=True),
            sa.Column("is_mandatory",    sa.Boolean(),   nullable=False, server_default="false"),
            sa.Column("deleted_at",      sa.DateTime(),  nullable=True),
            sa.Column("created_at",      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("created_by",      sa.Integer(),   sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_equipment_boat_id",   "boat_equipment_items", ["boat_id"])
        op.create_index("ix_equipment_category",  "boat_equipment_items", ["category"])
        op.create_index("ix_equipment_condition", "boat_equipment_items", ["condition"])

    # ── 6. boat_status_history (append-only) ──────────────────────────────────
    if not _table_exists("boat_status_history"):
        op.create_table(
            "boat_status_history",
            sa.Column("id",              sa.Integer(),  primary_key=True),
            sa.Column("boat_id",         sa.Integer(),  sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("previous_status", sa.String(30), nullable=True),
            sa.Column("new_status",      sa.String(30), nullable=False),
            sa.Column("reason",          sa.Text(),     nullable=True),
            sa.Column("actor_id",        sa.Integer(),  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source",          sa.String(30), nullable=False, server_default="manual"),
            sa.Column("created_at",      sa.DateTime(), nullable=False, server_default=sa.func.now()),
            # NO updated_at — this table is append-only
        )
        op.create_index("ix_status_history_boat_id", "boat_status_history", ["boat_id"])
        op.create_index("ix_status_history_created", "boat_status_history", ["created_at"])

    # ── 7. boat_audit_logs (append-only) ──────────────────────────────────────
    if not _table_exists("boat_audit_logs"):
        op.create_table(
            "boat_audit_logs",
            sa.Column("id",             sa.Integer(),    primary_key=True),
            sa.Column("boat_id",        sa.Integer(),    sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id",       sa.Integer(),    sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action",         sa.String(50),   nullable=False),
            sa.Column("target_table",   sa.String(60),   nullable=True),
            sa.Column("target_id",      sa.Integer(),    nullable=True),
            sa.Column("old_values",     sa.Text(),       nullable=True),   # JSON snapshot
            sa.Column("new_values",     sa.Text(),       nullable=True),   # JSON snapshot
            sa.Column("ip_address",     sa.String(45),   nullable=True),
            sa.Column("user_agent",     sa.String(255),  nullable=True),
            sa.Column("correlation_id", sa.String(64),   nullable=True),
            sa.Column("created_at",     sa.DateTime(),   nullable=False, server_default=sa.func.now()),
            # NEVER updated or deleted
        )
        op.create_index("ix_audit_boat_id",  "boat_audit_logs", ["boat_id"])
        op.create_index("ix_audit_actor",    "boat_audit_logs", ["actor_id"])
        op.create_index("ix_audit_action",   "boat_audit_logs", ["action"])
        op.create_index("ix_audit_created",  "boat_audit_logs", ["created_at"])

    # ── 8. boat_ownership_transfers ───────────────────────────────────────────
    if not _table_exists("boat_ownership_transfers"):
        op.create_table(
            "boat_ownership_transfers",
            sa.Column("id",               sa.Integer(),   primary_key=True),
            sa.Column("boat_id",          sa.Integer(),   sa.ForeignKey("boats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_owner_id",    sa.Integer(),   sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("to_owner_id",      sa.Integer(),   sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("transfer_date",    sa.Date(),      nullable=False),
            sa.Column("transfer_reason",  sa.String(50),  nullable=True),
            sa.Column("document_url",     sa.String(500), nullable=True),
            sa.Column("document_hash",    sa.String(64),  nullable=True),
            sa.Column("status",           sa.String(20),  nullable=False, server_default="pending"),
            sa.Column("approved_by",      sa.Integer(),   sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_at",      sa.DateTime(),  nullable=True),
            sa.Column("notes",            sa.Text(),      nullable=True),
            sa.Column("created_at",       sa.DateTime(),  nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at",       sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_transfers_boat_id", "boat_ownership_transfers", ["boat_id"])
        op.create_index("ix_transfers_status",  "boat_ownership_transfers", ["status"])

    # ── 9. Patch boat_maintenance ─────────────────────────────────────────────
    if _table_exists("boat_maintenance"):
        if not _col_exists("boat_maintenance", "status"):
            op.add_column("boat_maintenance", sa.Column(
                "status", sa.String(20), nullable=False, server_default="scheduled"
            ))
        if not _col_exists("boat_maintenance", "updated_at"):
            op.add_column("boat_maintenance", sa.Column(
                "updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
            ))
        # completed_by has a FK constraint — use batch_alter_table for SQLite compat
        if not _col_exists("boat_maintenance", "completed_by"):
            with op.batch_alter_table("boat_maintenance") as batch_op:
                batch_op.add_column(sa.Column("completed_by", sa.Integer()))
                batch_op.create_foreign_key(
                    "fk_boat_maintenance_completed_by", "users", ["completed_by"], ["id"]
                )
        if not _index_exists("ix_maintenance_status", "boat_maintenance"):
            op.create_index("ix_maintenance_status", "boat_maintenance", ["boat_id", "status"])
        if not _index_exists("ix_maintenance_scheduled_date", "boat_maintenance"):
            op.create_index("ix_maintenance_scheduled_date", "boat_maintenance", ["scheduled_date"])

    # ── 10. Patch boat_health_status — unique constraint on boat_id ───────────
    if _table_exists("boat_health_status") and not _unique_exists("boat_health_status", "boat_id"):
        # SQLite requires batch_alter_table to add constraints; PostgreSQL supports
        # ADD CONSTRAINT directly.  batch_alter_table works on both.
        with op.batch_alter_table("boat_health_status") as batch_op:
            batch_op.create_unique_constraint(
                "uq_boat_health_status_boat_id", ["boat_id"]
            )

    # ── 11. Patch boat_fuel_logs ──────────────────────────────────────────────
    if _table_exists("boat_fuel_logs"):
        # logged_by has a FK constraint — use batch_alter_table for SQLite compat
        if not _col_exists("boat_fuel_logs", "logged_by"):
            with op.batch_alter_table("boat_fuel_logs") as batch_op:
                batch_op.add_column(sa.Column("logged_by", sa.Integer()))
                batch_op.create_foreign_key(
                    "fk_boat_fuel_logs_logged_by", "users", ["logged_by"], ["id"]
                )


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    # Drop new tables in reverse FK dependency order
    for tbl in (
        "boat_ownership_transfers",
        "boat_audit_logs",
        "boat_status_history",
        "boat_equipment_items",
        "boat_inspections",
        "boat_crew_members",
        "boat_documents",
    ):
        if _table_exists(tbl):
            op.drop_table(tbl)

    # Remove patches from existing tables
    if _table_exists("boat_fuel_logs") and _col_exists("boat_fuel_logs", "logged_by"):
        with op.batch_alter_table("boat_fuel_logs") as batch_op:
            batch_op.drop_column("logged_by")

    if _table_exists("boat_maintenance"):
        for col in ("status", "completed_by", "updated_at"):
            if _col_exists("boat_maintenance", col):
                with op.batch_alter_table("boat_maintenance") as batch_op:
                    batch_op.drop_column(col)

    # Remove new boats columns (batch required for SQLite)
    boats_added = [
        "status", "vessel_class", "hull_material", "beam_meters", "draft_meters",
        "year_built", "engine_make", "engine_model", "engine_serial_number",
        "engine_year", "home_harbor_id", "verification_status", "verified_by",
        "verified_at", "qr_code_token", "photo_urls", "deleted_at", "version",
        "created_by", "updated_by",
    ]
    existing = {c["name"] for c in sa_inspect(op.get_bind()).get_columns("boats")}
    cols_to_drop = [c for c in boats_added if c in existing]
    if cols_to_drop:
        with op.batch_alter_table("boats") as batch_op:
            for col in cols_to_drop:
                batch_op.drop_column(col)
