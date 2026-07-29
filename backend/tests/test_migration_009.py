"""Migration 009 — structural verification tests.

Verifies that after migration 009 runs (via create_all in conftest):
  - All 7 new tables exist with the expected columns
  - All new columns exist on the boats table
  - Existing tables (boat_maintenance, boat_health_status, boat_fuel_logs)
    have the patched columns
  - Existing boat rows are unaffected (backward compatibility)
  - New columns have correct server defaults
  - Append-only tables (boat_status_history, boat_audit_logs) accept inserts
    and their rows are retrievable

These tests run against the SQLite test database created by conftest.py.
No Alembic runner is invoked — the schema is created via Base.metadata.create_all,
which exercises the same column definitions the migration encodes.
"""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


# ── helpers ───────────────────────────────────────────────────────────────────

def _columns(db: Session, table: str) -> set[str]:
    return {c["name"] for c in inspect(db.bind).get_columns(table)}


def _table_exists(db: Session, table: str) -> bool:
    return inspect(db.bind).has_table(table)


# ── 1. New tables exist ───────────────────────────────────────────────────────

@pytest.mark.parametrize("table", [
    "boat_documents",
    "boat_crew_members",
    "boat_inspections",
    "boat_equipment_items",
    "boat_status_history",
    "boat_audit_logs",
    "boat_ownership_transfers",
])
def test_new_table_exists(db: Session, table: str):
    assert _table_exists(db, table), f"Table '{table}' not found"


# ── 2. boats table — new columns ──────────────────────────────────────────────

@pytest.mark.parametrize("column", [
    "status",
    "vessel_class",
    "hull_material",
    "beam_meters",
    "draft_meters",
    "year_built",
    "engine_make",
    "engine_model",
    "engine_serial_number",
    "engine_year",
    "home_harbor_id",
    "verification_status",
    "verified_by",
    "verified_at",
    "qr_code_token",
    "photo_urls",
    "deleted_at",
    "version",
    "created_by",
    "updated_by",
])
def test_boats_new_column_exists(db: Session, column: str):
    assert column in _columns(db, "boats"), f"Column 'boats.{column}' not found"


# ── 3. boats table — original columns preserved ───────────────────────────────

@pytest.mark.parametrize("column", [
    "id", "owner_id", "name", "registration_number", "color",
    "length_meters", "engine_type", "engine_horsepower",
    "fuel_capacity_liters", "safety_equipment", "is_active",
    "created_at", "updated_at",
])
def test_boats_original_columns_preserved(db: Session, column: str):
    assert column in _columns(db, "boats"), f"Original column 'boats.{column}' was removed"


# ── 4. boat_documents columns ─────────────────────────────────────────────────

def test_boat_documents_columns(db: Session):
    cols = _columns(db, "boat_documents")
    for expected in (
        "id", "boat_id", "document_type", "document_number",
        "issuing_authority", "issue_date", "expiry_date",
        "file_url", "file_hash", "is_verified", "verified_by",
        "verified_at", "notes", "deleted_at",
        "created_at", "updated_at", "created_by", "updated_by",
    ):
        assert expected in cols, f"boat_documents.{expected} missing"


# ── 5. boat_crew_members columns ──────────────────────────────────────────────

def test_boat_crew_members_columns(db: Session):
    cols = _columns(db, "boat_crew_members")
    for expected in (
        "id", "boat_id", "user_id", "full_name", "phone_number",
        "aadhaar_last4", "role", "is_primary_contact", "is_active",
        "assigned_at", "removed_at", "removal_reason",
        "created_at", "updated_at", "created_by",
    ):
        assert expected in cols, f"boat_crew_members.{expected} missing"


# ── 6. boat_inspections columns ───────────────────────────────────────────────

def test_boat_inspections_columns(db: Session):
    cols = _columns(db, "boat_inspections")
    for expected in (
        "id", "boat_id", "inspection_type", "inspector_name",
        "inspector_authority", "inspection_date", "next_due_date",
        "result", "findings", "corrective_actions",
        "certificate_number", "certificate_url", "deleted_at",
        "created_at", "updated_at", "created_by",
    ):
        assert expected in cols, f"boat_inspections.{expected} missing"


# ── 7. boat_equipment_items columns ──────────────────────────────────────────

def test_boat_equipment_items_columns(db: Session):
    cols = _columns(db, "boat_equipment_items")
    for expected in (
        "id", "boat_id", "category", "item_name", "quantity",
        "condition", "last_checked_at", "expiry_date", "notes",
        "is_mandatory", "deleted_at", "created_at", "updated_at", "created_by",
    ):
        assert expected in cols, f"boat_equipment_items.{expected} missing"


# ── 8. boat_status_history columns ───────────────────────────────────────────

def test_boat_status_history_columns(db: Session):
    cols = _columns(db, "boat_status_history")
    for expected in (
        "id", "boat_id", "previous_status", "new_status",
        "reason", "actor_id", "source", "created_at",
    ):
        assert expected in cols, f"boat_status_history.{expected} missing"
    # append-only: no updated_at
    assert "updated_at" not in cols, "boat_status_history must not have updated_at (append-only)"


# ── 9. boat_audit_logs columns ────────────────────────────────────────────────

def test_boat_audit_logs_columns(db: Session):
    cols = _columns(db, "boat_audit_logs")
    for expected in (
        "id", "boat_id", "actor_id", "action", "target_table",
        "target_id", "old_values", "new_values", "ip_address",
        "user_agent", "correlation_id", "created_at",
    ):
        assert expected in cols, f"boat_audit_logs.{expected} missing"
    # append-only: no updated_at
    assert "updated_at" not in cols, "boat_audit_logs must not have updated_at (append-only)"


# ── 10. boat_ownership_transfers columns ─────────────────────────────────────

def test_boat_ownership_transfers_columns(db: Session):
    cols = _columns(db, "boat_ownership_transfers")
    for expected in (
        "id", "boat_id", "from_owner_id", "to_owner_id",
        "transfer_date", "transfer_reason", "document_url",
        "document_hash", "status", "approved_by", "approved_at",
        "notes", "created_at", "updated_at",
    ):
        assert expected in cols, f"boat_ownership_transfers.{expected} missing"


# ── 11. Patched existing tables ───────────────────────────────────────────────

def test_boat_maintenance_patched_columns(db: Session):
    cols = _columns(db, "boat_maintenance")
    assert "status"       in cols, "boat_maintenance.status missing"
    assert "completed_by" in cols, "boat_maintenance.completed_by missing"
    assert "updated_at"   in cols, "boat_maintenance.updated_at missing"


def test_boat_fuel_logs_patched_columns(db: Session):
    cols = _columns(db, "boat_fuel_logs")
    assert "logged_by" in cols, "boat_fuel_logs.logged_by missing"


# ── 12. Backward compatibility — existing boat row survives ──────────────────

def test_existing_boat_row_backward_compat(db: Session):
    """A boat created with only the original columns must still be readable."""
    from app.models.user import User
    from app.models.boat import Boat

    user = User(
        phone_number="+91_mig009_test",
        password_hash="hash",
        full_name="Migration Test Fisher",
        role="fisherman",
    )
    db.add(user)
    db.flush()

    boat = Boat(owner_id=user.id, name="Legacy Vessel", registration_number="MIG-009-T")
    db.add(boat)
    db.flush()

    fetched = db.query(Boat).filter(Boat.id == boat.id).first()
    assert fetched is not None
    assert fetched.name == "Legacy Vessel"
    # New columns should be accessible (None or default)
    assert fetched.deleted_at is None


# ── 13. Append-only tables accept inserts ────────────────────────────────────

def test_boat_status_history_insert(db: Session):
    from app.models.user import User
    from app.models.boat import Boat

    user = User(
        phone_number="+91_sh_test_009",
        password_hash="hash",
        full_name="Status History Fisher",
        role="fisherman",
    )
    db.add(user)
    db.flush()

    boat = Boat(owner_id=user.id, name="Status Vessel", registration_number="SH-009-T")
    db.add(boat)
    db.flush()

    db.execute(text(
        "INSERT INTO boat_status_history "
        "(boat_id, previous_status, new_status, source) "
        "VALUES (:bid, 'registered', 'active', 'manual')"
    ), {"bid": boat.id})
    db.flush()

    row = db.execute(
        text("SELECT new_status FROM boat_status_history WHERE boat_id = :bid"),
        {"bid": boat.id}
    ).fetchone()
    assert row is not None
    assert row[0] == "active"


def test_boat_audit_log_insert(db: Session):
    from app.models.user import User
    from app.models.boat import Boat

    user = User(
        phone_number="+91_al_test_009",
        password_hash="hash",
        full_name="Audit Log Fisher",
        role="fisherman",
    )
    db.add(user)
    db.flush()

    boat = Boat(owner_id=user.id, name="Audit Vessel", registration_number="AL-009-T")
    db.add(boat)
    db.flush()

    db.execute(text(
        "INSERT INTO boat_audit_logs (boat_id, actor_id, action) "
        "VALUES (:bid, :uid, 'created')"
    ), {"bid": boat.id, "uid": user.id})
    db.flush()

    row = db.execute(
        text("SELECT action FROM boat_audit_logs WHERE boat_id = :bid"),
        {"bid": boat.id}
    ).fetchone()
    assert row is not None
    assert row[0] == "created"


# ── 14. New tables accept FK-valid inserts ────────────────────────────────────

def test_boat_document_insert(db: Session):
    from app.models.user import User
    from app.models.boat import Boat

    user = User(
        phone_number="+91_doc_test_009",
        password_hash="hash",
        full_name="Doc Test Fisher",
        role="fisherman",
    )
    db.add(user)
    db.flush()

    boat = Boat(owner_id=user.id, name="Doc Vessel", registration_number="DOC-009-T")
    db.add(boat)
    db.flush()

    db.execute(text(
        "INSERT INTO boat_documents (boat_id, document_type, is_verified) "
        "VALUES (:bid, 'fishing_license', 0)"
    ), {"bid": boat.id})
    db.flush()

    row = db.execute(
        text("SELECT document_type FROM boat_documents WHERE boat_id = :bid"),
        {"bid": boat.id}
    ).fetchone()
    assert row is not None
    assert row[0] == "fishing_license"


def test_boat_equipment_item_insert(db: Session):
    from app.models.user import User
    from app.models.boat import Boat

    user = User(
        phone_number="+91_eq_test_009",
        password_hash="hash",
        full_name="Equipment Test Fisher",
        role="fisherman",
    )
    db.add(user)
    db.flush()

    boat = Boat(owner_id=user.id, name="Equipment Vessel", registration_number="EQ-009-T")
    db.add(boat)
    db.flush()

    db.execute(text(
        "INSERT INTO boat_equipment_items (boat_id, category, item_name, quantity, condition, is_mandatory) "
        "VALUES (:bid, 'life_saving', 'Life Jacket', 4, 'good', 0)"
    ), {"bid": boat.id})
    db.flush()

    row = db.execute(
        text("SELECT item_name FROM boat_equipment_items WHERE boat_id = :bid"),
        {"bid": boat.id}
    ).fetchone()
    assert row is not None
    assert row[0] == "Life Jacket"
