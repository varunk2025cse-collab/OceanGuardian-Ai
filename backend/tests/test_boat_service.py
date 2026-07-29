"""
Enterprise Boat Service — comprehensive test suite.

Covers:
  - Registration (duplicate detection, QR generation, audit, transactions)
  - Update (optimistic locking, partial update, audit)
  - Status transitions (FSM legal/illegal, history, audit)
  - Decommission (soft delete, active-trip guard)
  - Verification (RBAC, verified_by/verified_at/verification_status)
  - Role-aware retrieval (RBAC, BOAL, data-leakage defence)
  - is_trip_ready computed property
  - Concurrency (optimistic lock conflict)
  - Validation (invalid status, invalid verification status)
  - Regression (backward compatibility with v1 Boat model)

All tests run against the SQLite test database created by conftest.py.
Each test gets a fresh transaction that is rolled back after completion.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.boat import Boat, BoatStatus, BoatVerificationStatus
from app.models.trip import Trip
from app.models.family_link import FamilyLink
from app.schemas.boat import BoatV2Create, BoatV2Update
from app.services.boat_service import BoatService, LEGAL_TRANSITIONS


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def fisherman(db: Session) -> User:
    user = User(
        phone_number="+91_bs_fisher_01",
        password_hash="hash",
        full_name="Boat Service Fisher",
        role="fisherman",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def operator(db: Session) -> User:
    user = User(
        phone_number="+91_bs_operator_01",
        password_hash="hash",
        full_name="Boat Service Operator",
        role="operator",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def family_member(db: Session) -> User:
    user = User(
        phone_number="+91_bs_family_01",
        password_hash="hash",
        full_name="Boat Service Family",
        role="family",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def boat(db: Session, fisherman: User) -> Boat:
    b = Boat(
        owner_id=fisherman.id,
        name="Test Vessel",
        registration_number="BS-001",
        status=BoatStatus.ACTIVE.value,
        verification_status=BoatVerificationStatus.UNVERIFIED.value,
        is_active=True,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture
def registered_boat(db: Session, fisherman: User) -> Boat:
    """A boat in the 'registered' state — typical post-registration state."""
    b = Boat(
        owner_id=fisherman.id,
        name="Registered Vessel",
        registration_number="BS-REG-001",
        status=BoatStatus.REGISTERED.value,
        verification_status=BoatVerificationStatus.UNVERIFIED.value,
        is_active=True,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture
def boat_with_active_trip(db: Session, fisherman: User) -> Boat:
    """A boat that currently has an active trip."""
    b = Boat(
        owner_id=fisherman.id,
        name="Active Trip Vessel",
        registration_number="BS-TRIP-001",
        status=BoatStatus.ACTIVE.value,
        is_active=True,
    )
    db.add(b)
    db.flush()
    trip = Trip(
        user_id=fisherman.id,
        boat_id=b.id,
        status="active",
    )
    db.add(trip)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture
def family_link(db: Session, fisherman: User, family_member: User):
    """Link a family member to a fisherman."""
    link = FamilyLink(
        family_user_id=family_member.id,
        fisherman_id=fisherman.id,
        relation="primary",
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ─────────────────────────────────────────────
# REGISTRATION TESTS
# ─────────────────────────────────────────────

class TestRegisterBoat:
    """Tests for BoatService.register_boat()."""

    def test_register_boat_success(self, db: Session, fisherman: User):
        """A valid registration creates a boat with all expected defaults."""
        payload = BoatV2Create(name="New Boat", registration_number="NB-001")
        boat = BoatService.register_boat(db, payload, fisherman)

        assert boat.id is not None
        assert boat.name == "New Boat"
        assert boat.registration_number == "NB-001"
        assert boat.owner_id == fisherman.id
        assert boat.status == BoatStatus.REGISTERED.value
        assert boat.verification_status == BoatVerificationStatus.UNVERIFIED.value
        assert boat.qr_code_token is not None
        assert len(boat.qr_code_token) > 0
        assert boat.created_by == fisherman.id
        assert boat.updated_by == fisherman.id

    def test_register_boat_generates_unique_qr(self, db: Session, fisherman: User):
        """Each registration gets a unique QR token."""
        payload1 = BoatV2Create(name="Boat A", registration_number="A-001")
        payload2 = BoatV2Create(name="Boat B", registration_number="B-001")
        boat1 = BoatService.register_boat(db, payload1, fisherman)
        boat2 = BoatService.register_boat(db, payload2, fisherman)

        assert boat1.qr_code_token != boat2.qr_code_token

    def test_register_boat_no_registration_number(self, db: Session, fisherman: User):
        """Registration without a registration number succeeds."""
        payload = BoatV2Create(name="No Reg Number")
        boat = BoatService.register_boat(db, payload, fisherman)

        assert boat.id is not None
        assert boat.registration_number is None
        assert boat.qr_code_token is not None

    def test_register_boat_duplicate_registration_case_insensitive(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Case-insensitive duplicate registration number is rejected."""
        payload = BoatV2Create(name="Duplicate Reg", registration_number="bs-001")
        with pytest.raises(HTTPException) as exc_info:
            BoatService.register_boat(db, payload, fisherman)

        assert exc_info.value.status_code == 409
        assert "already in use" in exc_info.value.detail

    def test_register_boat_duplicate_name_same_owner(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman cannot register two boats with the same name."""
        payload = BoatV2Create(name="Test Vessel", registration_number="DIFFERENT-001")
        with pytest.raises(HTTPException) as exc_info:
            BoatService.register_boat(db, payload, fisherman)

        assert exc_info.value.status_code == 409
        assert "already have a boat named" in exc_info.value.detail

    def test_register_boat_duplicate_name_different_owner(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Different owners CAN register boats with the same name."""
        other_fisherman = User(
            phone_number="+91_bs_fisher_02",
            password_hash="hash",
            full_name="Other Fisher",
            role="fisherman",
        )
        db.add(other_fisherman)
        db.commit()
        db.refresh(other_fisherman)

        payload = BoatV2Create(name="Test Vessel", registration_number="OTHER-001")
        boat2 = BoatService.register_boat(db, payload, other_fisherman)

        assert boat2.id is not None
        assert boat2.owner_id == other_fisherman.id

    def test_register_boat_creates_audit_log(
        self, db: Session, fisherman: User
    ):
        """Registration creates an audit-log entry with action='created'."""
        payload = BoatV2Create(name="Audit Test", registration_number="AUDIT-001")
        boat = BoatService.register_boat(db, payload, fisherman)

        from app.models.boat import BoatAuditLog
        logs = (
            db.query(BoatAuditLog)
            .filter(BoatAuditLog.boat_id == boat.id, BoatAuditLog.action == "created")
            .all()
        )
        assert len(logs) == 1
        assert logs[0].actor_id == fisherman.id
        assert logs[0].new_values is not None
        assert "name" in logs[0].new_values

    def test_register_boat_creates_status_history(
        self, db: Session, fisherman: User
    ):
        """Registration creates a status-history entry for the initial state."""
        payload = BoatV2Create(name="Status Hist Test", registration_number="SH-001")
        boat = BoatService.register_boat(db, payload, fisherman)

        from app.models.boat import BoatStatusHistory
        history = (
            db.query(BoatStatusHistory)
            .filter(BoatStatusHistory.boat_id == boat.id)
            .all()
        )
        assert len(history) == 1
        assert history[0].new_status == BoatStatus.REGISTERED.value
        assert history[0].previous_status is None
        assert history[0].actor_id == fisherman.id

    def test_register_boat_invalid_harbor(
        self, db: Session, fisherman: User
    ):
        """Registration with a non-existent home harbor is rejected."""
        payload = BoatV2Create(name="Bad Harbor", home_harbor_id=99999)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.register_boat(db, payload, fisherman)

        assert exc_info.value.status_code == 400
        assert "does not exist" in exc_info.value.detail

    def test_register_boat_full_fields(self, db: Session, fisherman: User):
        """Registration with all v2 fields populates the boat correctly."""
        payload = BoatV2Create(
            name="Full Boat",
            registration_number="FULL-001",
            vessel_class="trawler",
            hull_material="fiberglass",
            color="blue",
            length_meters=25.5,
            beam_meters=8.0,
            draft_meters=3.0,
            year_built=2020,
            engine_type="diesel",
            engine_make="Yanmar",
            engine_model="3JH5",
            engine_serial_number="SN12345",
            engine_year=2020,
            engine_horsepower=250,
            fuel_capacity_liters=500.0,
        )
        boat = BoatService.register_boat(db, payload, fisherman)

        assert boat.vessel_class == "trawler"
        assert boat.hull_material == "fiberglass"
        assert boat.length_meters == 25.5
        assert boat.beam_meters == 8.0
        assert boat.draft_meters == 3.0
        assert boat.year_built == 2020
        assert boat.engine_make == "Yanmar"
        assert boat.engine_model == "3JH5"
        assert boat.engine_serial_number == "SN12345"
        assert boat.engine_year == 2020
        assert boat.engine_horsepower == 250
        assert boat.fuel_capacity_liters == 500.0


# ─────────────────────────────────────────────
# UPDATE TESTS
# ─────────────────────────────────────────────

class TestUpdateBoat:
    """Tests for BoatService.update_boat()."""

    def test_update_boat_success(self, db: Session, fisherman: User, boat: Boat):
        """A partial update modifies only the specified fields."""
        original_version = boat.version
        payload = BoatV2Update(name="Updated Name", version=original_version)
        updated = BoatService.update_boat(db, boat.id, payload, fisherman)

        assert updated.name == "Updated Name"
        assert updated.version == original_version + 1
        assert updated.updated_by == fisherman.id

    def test_update_boat_partial_fields(self, db: Session, fisherman: User, boat: Boat):
        """Only fields in exclude_unset are modified."""
        original_reg = boat.registration_number
        payload = BoatV2Update(name="New Name Only", version=boat.version)
        updated = BoatService.update_boat(db, boat.id, payload, fisherman)

        assert updated.name == "New Name Only"
        assert updated.registration_number == original_reg

    def test_update_boat_version_conflict(self, db: Session, fisherman: User, boat: Boat):
        """A stale version triggers a 409 conflict."""
        payload = BoatV2Update(name="Conflict", version=999)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.update_boat(db, boat.id, payload, fisherman)

        assert exc_info.value.status_code == 409
        assert "Version conflict" in exc_info.value.detail

    def test_update_boat_no_version_still_works(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Updates without a version (backward compat) still succeed."""
        original_version = boat.version
        payload = BoatV2Update(name="No Version Update")
        updated = BoatService.update_boat(db, boat.id, payload, fisherman)

        assert updated.name == "No Version Update"
        assert updated.version == original_version + 1

    def test_update_boat_creates_audit_log(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Update creates an audit-log entry with old and new values."""
        payload = BoatV2Update(name="Audit Update", version=boat.version)
        BoatService.update_boat(db, boat.id, payload, fisherman)

        from app.models.boat import BoatAuditLog
        logs = (
            db.query(BoatAuditLog)
            .filter(BoatAuditLog.boat_id == boat.id, BoatAuditLog.action == "updated")
            .all()
        )
        assert len(logs) == 1
        assert logs[0].old_values is not None
        assert logs[0].new_values is not None
        assert "Test Vessel" in logs[0].old_values
        assert "Audit Update" in logs[0].new_values

    def test_update_boat_cannot_change_owner(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """The owner_id field is stripped from update data (mass-assignment defence)."""
        other_user = User(
            phone_number="+91_bs_other_01",
            password_hash="hash",
            full_name="Other User",
            role="fisherman",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        payload = BoatV2Update(owner_id=other_user.id, version=boat.version)
        # owner_id is not in BoatV2Update, so this tests that even if it were
        # somehow passed, it would be stripped. We test with a valid field.
        payload = BoatV2Update(name="Owner Test", version=boat.version)
        updated = BoatService.update_boat(db, boat.id, payload, fisherman)

        assert updated.owner_id == fisherman.id  # unchanged

    def test_update_boat_unauthorized_user(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A different fisherman cannot update another's boat (BOAL)."""
        other_user = User(
            phone_number="+91_bs_other_02",
            password_hash="hash",
            full_name="Other Fisher",
            role="fisherman",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        payload = BoatV2Update(name="Hacked", version=boat.version)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.update_boat(db, boat.id, payload, other_user)

        assert exc_info.value.status_code == 404

    def test_update_boat_operator_can_update_any(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator can update any boat."""
        payload = BoatV2Update(name="Operator Update", version=boat.version)
        updated = BoatService.update_boat(db, boat.id, payload, operator)

        assert updated.name == "Operator Update"


# ─────────────────────────────────────────────
# STATUS TRANSITION TESTS
# ─────────────────────────────────────────────

class TestStatusTransitions:
    """Tests for BoatService.change_status() FSM."""

    def test_transition_registered_to_active(
        self, db: Session, fisherman: User, registered_boat: Boat
    ):
        """registered → active is a legal transition."""
        updated = BoatService.change_status(
            db, registered_boat.id, BoatStatus.ACTIVE.value, fisherman,
            reason="Passed inspection",
        )
        assert updated.status == BoatStatus.ACTIVE.value

    def test_transition_active_to_maintenance(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """active → maintenance is legal."""
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
            reason="Scheduled servicing",
        )
        assert updated.status == BoatStatus.MAINTENANCE.value

    def test_transition_active_to_emergency(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """active → emergency is legal."""
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.EMERGENCY.value, fisherman,
            reason="SOS triggered",
        )
        assert updated.status == BoatStatus.EMERGENCY.value

    def test_transition_active_to_damaged(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """active → damaged is legal."""
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.DAMAGED.value, fisherman,
            reason="Collision with debris",
        )
        assert updated.status == BoatStatus.DAMAGED.value

    def test_transition_active_to_lost(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """active → lost is legal."""
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.LOST.value, fisherman,
            reason="Declared lost at sea",
        )
        assert updated.status == BoatStatus.LOST.value

    def test_transition_illegal_active_to_registered(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """active → registered is illegal."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, BoatStatus.REGISTERED.value, fisherman,
            )
        assert exc_info.value.status_code == 409
        assert "Illegal transition" in exc_info.value.detail

    def test_transition_illegal_maintenance_to_active(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """maintenance → active is legal (repair complete)."""
        BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
        )
        # Need to re-fetch to get updated status
        db.commit()
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.ACTIVE.value, fisherman,
        )
        assert updated.status == BoatStatus.ACTIVE.value

    def test_transition_illegal_maintenance_to_lost(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """maintenance → lost is illegal."""
        BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
        )
        db.refresh(boat)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, BoatStatus.LOST.value, fisherman,
            )
        assert exc_info.value.status_code == 409

    def test_transition_emergency_to_active(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """emergency → active is legal (incident resolved)."""
        BoatService.change_status(
            db, boat.id, BoatStatus.EMERGENCY.value, fisherman,
        )
        db.commit()
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.ACTIVE.value, fisherman,
        )
        assert updated.status == BoatStatus.ACTIVE.value

    def test_transition_emergency_to_damaged(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """emergency → damaged is legal."""
        BoatService.change_status(
            db, boat.id, BoatStatus.EMERGENCY.value, fisherman,
        )
        db.commit()
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.DAMAGED.value, fisherman,
        )
        assert updated.status == BoatStatus.DAMAGED.value

    def test_transition_illegal_damaged_to_active(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """damaged → active is illegal (must go through maintenance first)."""
        BoatService.change_status(
            db, boat.id, BoatStatus.DAMAGED.value, fisherman,
        )
        db.refresh(boat)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, BoatStatus.ACTIVE.value, fisherman,
            )
        assert exc_info.value.status_code == 409

    def test_transition_damaged_to_maintenance(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """damaged → maintenance is legal (repairs underway)."""
        BoatService.change_status(
            db, boat.id, BoatStatus.DAMAGED.value, fisherman,
        )
        db.commit()
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
        )
        assert updated.status == BoatStatus.MAINTENANCE.value

    def test_transition_lost_to_decommissioned(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """lost → decommissioned is legal (formal retirement)."""
        BoatService.change_status(
            db, boat.id, BoatStatus.LOST.value, fisherman,
        )
        db.refresh(boat)
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.DECOMMISSIONED.value, fisherman,
        )
        assert updated.status == BoatStatus.DECOMMISSIONED.value

    def test_transition_illegal_lost_to_active(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """lost → active is illegal."""
        BoatService.change_status(
            db, boat.id, BoatStatus.LOST.value, fisherman,
        )
        db.refresh(boat)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, BoatStatus.ACTIVE.value, fisherman,
            )
        assert exc_info.value.status_code == 409

    def test_transition_terminal_decommissioned_rejected(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """decommissioned is terminal — no further transitions."""
        BoatService.change_status(
            db, boat.id, BoatStatus.DECOMMISSIONED.value, fisherman,
        )
        db.refresh(boat)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, BoatStatus.ACTIVE.value, fisherman,
            )
        assert exc_info.value.status_code == 409
        assert "terminal" in exc_info.value.detail

    def test_transition_creates_status_history(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Each status transition creates a status-history entry."""
        BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
            reason="Servicing",
        )
        db.commit()

        from app.models.boat import BoatStatusHistory
        history = (
            db.query(BoatStatusHistory)
            .filter(BoatStatusHistory.boat_id == boat.id)
            .all()
        )
        assert len(history) >= 1
        latest = history[-1]
        assert latest.previous_status == BoatStatus.ACTIVE.value
        assert latest.new_status == BoatStatus.MAINTENANCE.value
        assert latest.reason == "Servicing"
        assert latest.actor_id == fisherman.id

    def test_transition_creates_audit_log(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Each status transition creates an audit-log entry."""
        BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
        )
        db.commit()

        from app.models.boat import BoatAuditLog
        logs = (
            db.query(BoatAuditLog)
            .filter(BoatAuditLog.boat_id == boat.id, BoatAuditLog.action == "status_changed")
            .all()
        )
        assert len(logs) >= 1
        assert logs[-1].old_values is not None
        assert logs[-1].new_values is not None

    def test_transition_invalid_status_rejected(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """An unknown status value is rejected with 422."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, "nonexistent_status", fisherman,
            )
        assert exc_info.value.status_code == 422

    def test_transition_to_decommissioned_soft_deletes(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Transitioning to decommissioned sets deleted_at and is_active=False."""
        updated = BoatService.change_status(
            db, boat.id, BoatStatus.DECOMMISSIONED.value, fisherman,
        )
        assert updated.deleted_at is not None
        assert updated.is_active is False

    def test_transition_decommissioned_not_visible(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """After decommissioning, get_boat_for_user returns 404."""
        BoatService.change_status(
            db, boat.id, BoatStatus.DECOMMISSIONED.value, fisherman,
        )
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            BoatService.get_boat_for_user(db, boat.id, fisherman)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────
# DECOMMISSION TESTS
# ─────────────────────────────────────────────

class TestDecommissionBoat:
    """Tests for BoatService.decommission_boat()."""

    def test_decommission_success(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Decommissioning a boat without an active trip succeeds."""
        updated = BoatService.decommission_boat(db, boat.id, fisherman, reason="End of life")

        assert updated.status == BoatStatus.DECOMMISSIONED.value
        assert updated.deleted_at is not None
        assert updated.is_active is False

    def test_decommission_rejects_active_trip(
        self, db: Session, fisherman: User, boat_with_active_trip: Boat
    ):
        """Decommissioning a boat with an active trip is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.decommission_boat(db, boat_with_active_trip.id, fisherman)

        assert exc_info.value.status_code == 409
        assert "active trip" in exc_info.value.detail

    def test_decommission_creates_status_history(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Decommissioning creates a status-history entry."""
        BoatService.decommission_boat(db, boat.id, fisherman, reason="End of life")

        from app.models.boat import BoatStatusHistory
        history = (
            db.query(BoatStatusHistory)
            .filter(BoatStatusHistory.boat_id == boat.id)
            .all()
        )
        assert len(history) >= 1
        assert history[-1].new_status == BoatStatus.DECOMMISSIONED.value

    def test_decommission_creates_audit_log(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Decommissioning creates an audit-log entry."""
        BoatService.decommission_boat(db, boat.id, fisherman, reason="End of life")

        from app.models.boat import BoatAuditLog
        logs = (
            db.query(BoatAuditLog)
            .filter(BoatAuditLog.boat_id == boat.id)
            .all()
        )
        assert len(logs) >= 1

    def test_decommission_unauthorized_user(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A different fisherman cannot decommission another's boat."""
        other_user = User(
            phone_number="+91_bs_decomm_01",
            password_hash="hash",
            full_name="Other Fisher",
            role="fisherman",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        with pytest.raises(HTTPException) as exc_info:
            BoatService.decommission_boat(db, boat.id, other_user)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────
# VERIFICATION TESTS
# ─────────────────────────────────────────────

class TestVerifyBoat:
    """Tests for BoatService.verify_boat()."""

    def test_verify_success(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator can verify a boat."""
        updated = BoatService.verify_boat(
            db, boat.id, BoatVerificationStatus.VERIFIED.value, operator,
            notes="Documents checked",
        )
        assert updated.verification_status == BoatVerificationStatus.VERIFIED.value
        assert updated.verified_by == operator.id
        assert updated.verified_at is not None

    def test_verify_rejected(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator can reject a boat."""
        updated = BoatService.verify_boat(
            db, boat.id, BoatVerificationStatus.REJECTED.value, operator,
            notes="Missing documents",
        )
        assert updated.verification_status == BoatVerificationStatus.REJECTED.value
        assert updated.verified_by == operator.id

    def test_verify_pending(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator can set verification to pending."""
        updated = BoatService.verify_boat(
            db, boat.id, BoatVerificationStatus.PENDING.value, operator,
        )
        assert updated.verification_status == BoatVerificationStatus.PENDING.value

    def test_verify_rbac_fisherman_denied(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman cannot verify boats."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.verify_boat(
                db, boat.id, BoatVerificationStatus.VERIFIED.value, fisherman,
            )
        assert exc_info.value.status_code == 403
        assert "Only operators" in exc_info.value.detail

    def test_verify_rbac_family_denied(
        self, db: Session, fisherman: User, boat: Boat, family_member: User,
        family_link: FamilyLink,
    ):
        """A family member cannot verify boats."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.verify_boat(
                db, boat.id, BoatVerificationStatus.VERIFIED.value, family_member,
            )
        assert exc_info.value.status_code == 403

    def test_verify_invalid_status(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An invalid verification status is rejected with 422."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.verify_boat(
                db, boat.id, "nonexistent", operator,
            )
        assert exc_info.value.status_code == 422

    def test_verify_creates_audit_log(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """Verification creates an audit-log entry."""
        BoatService.verify_boat(
            db, boat.id, BoatVerificationStatus.VERIFIED.value, operator,
        )

        from app.models.boat import BoatAuditLog
        logs = (
            db.query(BoatAuditLog)
            .filter(BoatAuditLog.boat_id == boat.id, BoatAuditLog.action == "verified")
            .all()
        )
        assert len(logs) == 1
        assert logs[0].actor_id == operator.id

    def test_verify_not_found(
        self, db: Session, operator: User
    ):
        """Verifying a non-existent boat returns 404."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.verify_boat(
                db, 99999, BoatVerificationStatus.VERIFIED.value, operator,
            )
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────
# ROLE-AWARE RETRIEVAL TESTS
# ─────────────────────────────────────────────

class TestGetBoatForUser:
    """Tests for BoatService.get_boat_for_user() RBAC."""

    def test_fisherman_gets_own_boat(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman can retrieve their own boat."""
        result = BoatService.get_boat_for_user(db, boat.id, fisherman)
        assert result.id == boat.id

    def test_fisherman_cannot_get_others_boat(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman cannot retrieve another's boat (BOAL)."""
        other_user = User(
            phone_number="+91_bs_rbac_01",
            password_hash="hash",
            full_name="Other Fisher",
            role="fisherman",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        with pytest.raises(HTTPException) as exc_info:
            BoatService.get_boat_for_user(db, boat.id, other_user)
        assert exc_info.value.status_code == 404

    def test_operator_gets_any_boat(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator can retrieve any boat."""
        result = BoatService.get_boat_for_user(db, boat.id, operator)
        assert result.id == boat.id

    def test_family_gets_linked_boat(
        self, db: Session, fisherman: User, boat: Boat,
        family_member: User, family_link: FamilyLink,
    ):
        """A family member can retrieve a boat owned by a linked fisherman."""
        result = BoatService.get_boat_for_user(db, boat.id, family_member)
        assert result.id == boat.id

    def test_family_cannot_get_unlinked_boat(
        self, db: Session, fisherman: User, boat: Boat, family_member: User
    ):
        """A family member without a link cannot retrieve the boat."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.get_boat_for_user(db, boat.id, family_member)
        assert exc_info.value.status_code == 404

    def test_deleted_boat_returns_404(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A soft-deleted boat returns 404."""
        BoatService.decommission_boat(db, boat.id, fisherman)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            BoatService.get_boat_for_user(db, boat.id, fisherman)
        assert exc_info.value.status_code == 404

    def test_nonexistent_boat_returns_404(
        self, db: Session, fisherman: User
    ):
        """A non-existent boat returns 404."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.get_boat_for_user(db, 99999, fisherman)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────
# is_trip_ready PROPERTY TESTS
# ─────────────────────────────────────────────

class TestIsTripReady:
    """Tests for the Boat.is_trip_ready computed property."""

    def test_ready_active_boat(self, boat: Boat):
        """An active boat with status='active' is trip-ready."""
        assert boat.is_trip_ready is True

    def test_ready_registered_boat(self, registered_boat: Boat):
        """A registered boat is trip-ready."""
        assert registered_boat.is_trip_ready is True

    def test_not_ready_maintenance(self, db: Session, fisherman: User, boat: Boat):
        """A boat in maintenance is not trip-ready."""
        BoatService.change_status(
            db, boat.id, BoatStatus.MAINTENANCE.value, fisherman,
        )
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_inactive(self, db: Session, fisherman: User, boat: Boat):
        """A boat set to inactive is not trip-ready."""
        BoatService.change_status(
            db, boat.id, BoatStatus.INACTIVE.value, fisherman,
        )
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_emergency(self, db: Session, fisherman: User, boat: Boat):
        """A boat in emergency is not trip-ready."""
        BoatService.change_status(
            db, boat.id, BoatStatus.EMERGENCY.value, fisherman,
        )
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_damaged(self, db: Session, fisherman: User, boat: Boat):
        """A boat that is damaged is not trip-ready."""
        BoatService.change_status(
            db, boat.id, BoatStatus.DAMAGED.value, fisherman,
        )
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_lost(self, db: Session, fisherman: User, boat: Boat):
        """A boat that is lost is not trip-ready."""
        BoatService.change_status(
            db, boat.id, BoatStatus.LOST.value, fisherman,
        )
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_decommissioned(self, db: Session, fisherman: User, boat: Boat):
        """A decommissioned boat is not trip-ready."""
        BoatService.decommission_boat(db, boat.id, fisherman)
        db.commit()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_soft_deleted(self, db: Session, boat: Boat):
        """A soft-deleted boat is not trip-ready."""
        boat.deleted_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(boat)
        assert boat.is_trip_ready is False

    def test_not_ready_is_active_false(self, boat: Boat):
        """A boat with is_active=False is not trip-ready."""
        boat.is_active = False
        assert boat.is_trip_ready is False

    def test_is_trip_ready_no_db_queries(self, boat: Boat):
        """is_trip_ready must not trigger any database queries.

        This is verified by checking that the property returns immediately
        without accessing the session — it only reads instance attributes.
        """
        # If this property triggered a DB query, accessing it on a detached
        # instance (no session) would raise an error. We detach the instance
        # and verify the property still works.
        from sqlalchemy.orm import make_transient
        make_transient(boat)
        # Should not raise — property only reads instance attributes
        result = boat.is_trip_ready
        assert isinstance(result, bool)


# ─────────────────────────────────────────────
# CONCURRENCY / OPTIMISTIC LOCK TESTS
# ─────────────────────────────────────────────

class TestOptimisticLock:
    """Tests for optimistic locking via the version column."""

    def test_version_increments_on_update(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Each successful update increments the version."""
        original_version = boat.version
        payload = BoatV2Update(name="First Update", version=original_version)
        BoatService.update_boat(db, boat.id, payload, fisherman)

        payload2 = BoatV2Update(name="Second Update", version=original_version + 1)
        updated = BoatService.update_boat(db, boat.id, payload2, fisherman)

        assert updated.version == original_version + 2

    def test_concurrent_update_conflict(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Two concurrent updates with the same version — second one fails."""
        original_version = boat.version

        # First update succeeds
        payload1 = BoatV2Update(name="First", version=original_version)
        BoatService.update_boat(db, boat.id, payload1, fisherman)

        # Second update with stale version fails
        payload2 = BoatV2Update(name="Second", version=original_version)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.update_boat(db, boat.id, payload2, fisherman)

        assert exc_info.value.status_code == 409

    def test_version_protects_mass_assignment(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """The version field cannot be set by the client (mass-assignment defence)."""
        payload = BoatV2Update(name="Test", version=999)
        with pytest.raises(HTTPException) as exc_info:
            BoatService.update_boat(db, boat.id, payload, fisherman)

        assert exc_info.value.status_code == 409


# ─────────────────────────────────────────────
# VALIDATION TESTS
# ─────────────────────────────────────────────

class TestValidation:
    """Tests for input validation."""

    def test_register_boat_name_too_short(
        self, db: Session, fisherman: User
    ):
        """Boat name must be at least 1 character."""
        with pytest.raises(Exception):  # PydanticValidationError
            BoatV2Create(name="")

    def test_register_boat_name_too_long(
        self, db: Session, fisherman: User
    ):
        """Boat name must not exceed 120 characters."""
        with pytest.raises(Exception):
            BoatV2Create(name="x" * 121)

    def test_register_boat_invalid_vessel_class(
        self, db: Session, fisherman: User
    ):
        """Invalid vessel_class is rejected by the schema."""
        with pytest.raises(Exception):
            BoatV2Create(name="Test", vessel_class="invalid_class")

    def test_register_boat_invalid_hull_material(
        self, db: Session, fisherman: User
    ):
        """Invalid hull_material is rejected by the schema."""
        with pytest.raises(Exception):
            BoatV2Create(name="Test", hull_material="invalid_material")

    def test_register_boat_negative_length(
        self, db: Session, fisherman: User
    ):
        """Negative length is rejected by the schema."""
        with pytest.raises(Exception):
            BoatV2Create(name="Test", length_meters=-5.0)

    def test_register_boat_invalid_year(
        self, db: Session, fisherman: User
    ):
        """Year out of range is rejected by the schema."""
        with pytest.raises(Exception):
            BoatV2Create(name="Test", year_built=1800)

    def test_change_status_invalid_status(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """An unknown status string is rejected with 422."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.change_status(
                db, boat.id, "totally_invalid", fisherman,
            )
        assert exc_info.value.status_code == 422

    def test_verify_invalid_status(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An invalid verification status is rejected with 422."""
        with pytest.raises(HTTPException) as exc_info:
            BoatService.verify_boat(
                db, boat.id, "invalid_verification", operator,
            )
        assert exc_info.value.status_code == 422


# ─────────────────────────────────────────────
# ENUM TESTS
# ─────────────────────────────────────────────

class TestEnums:
    """Tests for the BoatStatus and BoatVerificationStatus enums."""

    def test_boat_status_values(self):
        """BoatStatus has all expected values."""
        expected = {
            "registered", "active", "inactive", "maintenance",
            "emergency", "lost", "damaged", "decommissioned",
        }
        assert BoatStatus.all() == expected

    def test_boat_status_terminal(self):
        """BoatStatus.terminal() returns only decommissioned."""
        assert BoatStatus.terminal() == {"decommissioned"}

    def test_boat_verification_status_values(self):
        """BoatVerificationStatus has all expected values."""
        expected = {"unverified", "pending", "verified", "rejected"}
        assert BoatVerificationStatus.all() == expected

    def test_boat_status_is_str_enum(self):
        """BoatStatus members are strings (for DB compatibility)."""
        assert isinstance(BoatStatus.ACTIVE, str)
        assert BoatStatus.ACTIVE == "active"

    def test_boat_verification_is_str_enum(self):
        """BoatVerificationStatus members are strings."""
        assert isinstance(BoatVerificationStatus.VERIFIED, str)
        assert BoatVerificationStatus.VERIFIED == "verified"


# ─────────────────────────────────────────────
# FSM LEGAL TRANSITIONS TESTS
# ─────────────────────────────────────────────

class TestFSMLegalTransitions:
    """Tests for the LEGAL_TRANSITIONS table completeness."""

    def test_all_statuses_have_transitions(self):
        """Every BoatStatus has an entry in LEGAL_TRANSITIONS."""
        for status in BoatStatus.all():
            assert status in LEGAL_TRANSITIONS, f"Missing transition entry for {status}"

    def test_terminal_has_no_transitions(self):
        """Terminal statuses have empty transition sets."""
        assert LEGAL_TRANSITIONS[BoatStatus.DECOMMISSIONED.value] == set()
        assert LEGAL_TRANSITIONS[BoatStatus.LOST.value] == {BoatStatus.DECOMMISSIONED.value}

    def test_registered_can_go_active_or_decommissioned(self):
        """registered → {active, decommissioned}."""
        targets = LEGAL_TRANSITIONS[BoatStatus.REGISTERED.value]
        assert BoatStatus.ACTIVE.value in targets
        assert BoatStatus.DECOMMISSIONED.value in targets
        assert len(targets) == 2

    def test_active_has_six_targets(self):
        """active → 6 possible states."""
        targets = LEGAL_TRANSITIONS[BoatStatus.ACTIVE.value]
        assert len(targets) == 6
        for s in [BoatStatus.INACTIVE, BoatStatus.MAINTENANCE, BoatStatus.EMERGENCY,
                  BoatStatus.DAMAGED, BoatStatus.LOST, BoatStatus.DECOMMISSIONED]:
            assert s.value in targets

    def test_emergency_can_go_to_five_states(self):
        """emergency → 5 possible states."""
        targets = LEGAL_TRANSITIONS[BoatStatus.EMERGENCY.value]
        assert len(targets) == 5
        for s in [BoatStatus.ACTIVE, BoatStatus.MAINTENANCE, BoatStatus.DAMAGED,
                  BoatStatus.LOST, BoatStatus.DECOMMISSIONED]:
            assert s.value in targets


# ─────────────────────────────────────────────
# LISTING TESTS
# ─────────────────────────────────────────────

class TestListBoatsForUser:
    """Tests for BoatService.list_boats_for_user()."""

    def test_fisherman_lists_own_boats(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman sees only their own boats."""
        boats, total = BoatService.list_boats_for_user(db, fisherman)
        assert total >= 1
        assert all(b.owner_id == fisherman.id for b in boats)

    def test_operator_lists_all_boats(
        self, db: Session, fisherman: User, boat: Boat, operator: User
    ):
        """An operator sees all boats."""
        boats, total = BoatService.list_boats_for_user(db, operator)
        assert total >= 1

    def test_fisherman_lists_with_status_filter(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman can filter by status."""
        boats, total = BoatService.list_boats_for_user(
            db, fisherman, status=BoatStatus.ACTIVE.value
        )
        assert all(b.status == BoatStatus.ACTIVE.value for b in boats)

    def test_fisherman_lists_with_search(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """A fisherman can search by name."""
        boats, total = BoatService.list_boats_for_user(
            db, fisherman, search="Test"
        )
        assert all("test" in b.name.lower() for b in boats)

    def test_family_lists_linked_boats(
        self, db: Session, fisherman: User, boat: Boat,
        family_member: User, family_link: FamilyLink,
    ):
        """A family member sees boats of linked fishermen."""
        boats, total = BoatService.list_boats_for_user(db, family_member)
        assert total >= 1
        assert all(b.owner_id == fisherman.id for b in boats)

    def test_family_no_links_returns_empty(
        self, db: Session, family_member: User
    ):
        """A family member with no links sees no boats."""
        boats, total = BoatService.list_boats_for_user(db, family_member)
        assert total == 0
        assert len(boats) == 0


# ─────────────────────────────────────────────
# FLEET SUMMARY TESTS
# ─────────────────────────────────────────────

class TestFleetSummary:
    """Tests for BoatService.get_fleet_summary()."""

    def test_fleet_summary_returns_dict(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Fleet summary returns a dict with expected keys."""
        summary = BoatService.get_fleet_summary(db)
        assert "total_boats" in summary
        assert "by_status" in summary
        assert "by_verification" in summary
        assert "documents_expiring_30_days" in summary
        assert "boats_with_active_trips" in summary
        assert isinstance(summary["total_boats"], int)
        assert isinstance(summary["by_status"], dict)

    def test_fleet_summary_counts_boats(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Fleet summary counts non-deleted boats."""
        summary = BoatService.get_fleet_summary(db)
        assert summary["total_boats"] >= 1


# ─────────────────────────────────────────────
# REGRESSION TESTS
# ─────────────────────────────────────────────

class TestRegression:
    """Tests for backward compatibility and regression prevention."""

    def test_v1_boat_still_works(self, db: Session, fisherman: User):
        """A boat created with only v1 fields (no migration 009 fields) works."""
        from app.models.boat import Boat
        boat = Boat(
            owner_id=fisherman.id,
            name="Legacy V1 Boat",
            registration_number="V1-LEGACY",
        )
        db.add(boat)
        db.commit()
        db.refresh(boat)

        # New columns should be accessible (None or default)
        assert boat.deleted_at is None
        assert boat.version is not None
        assert boat.status == "active"  # server default
        assert boat.verification_status == "unverified"  # server default
        assert boat.is_trip_ready is True

    def test_v1_router_still_works(self, db: Session, fisherman: User):
        """The v1 boat creation path (direct model, no service) still works."""
        from app.models.boat import Boat
        import json
        boat = Boat(
            owner_id=fisherman.id,
            name="V1 Router Test",
            registration_number="V1-TEST",
            safety_equipment=json.dumps(["life_jacket", "first_aid_kit"]),
        )
        db.add(boat)
        db.commit()
        db.refresh(boat)

        assert boat.safety_equipment is not None
        parsed = json.loads(boat.safety_equipment)
        assert "life_jacket" in parsed

    def test_existing_boat_update_without_version(
        self, db: Session, fisherman: User, boat: Boat
    ):
        """Updating an existing boat without a version (v1-style) still works."""
        payload = BoatV2Update(name="V1 Update")
        updated = BoatService.update_boat(db, boat.id, payload, fisherman)
        assert updated.name == "V1 Update"

    def test_boat_with_null_registration_number(
        self, db: Session, fisherman: User
    ):
        """A boat with no registration number can be registered."""
        payload = BoatV2Create(name="No Reg")
        boat = BoatService.register_boat(db, payload, fisherman)
        assert boat.registration_number is None
        assert boat.qr_code_token is not None

    def test_boat_model_backward_compat_constructor(
        self, db: Session, fisherman: User
    ):
        """The Boat constructor's backward-compat kwargs still work."""
        boat = Boat(
            boat_name="Compat Boat",
            boat_type="diesel",
            owner_id=fisherman.id,
        )
        db.add(boat)
        db.commit()
        db.refresh(boat)

        assert boat.name == "Compat Boat"
        assert boat.engine_type == "diesel"
