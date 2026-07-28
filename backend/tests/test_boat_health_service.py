"""Fuel & Boat Health Service Tests — Phase 5 Week 2.

Tests cover fuel log creation, fuel summary, maintenance, and health score.
Adapted to match actual BoatHealthService interface.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.boat import Boat
from app.models.phase5 import BoatHealthStatus
from app.services.boat_health import (
    BoatHealthService,
    FuelLogCreate,
    MaintenanceCreate,
    FuelSummaryResponse,
    HealthScoreResponse,
)


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def fisherman(db: Session) -> User:
    user = User(
        phone_number="+91_bh_001",
        password_hash="hash",
        full_name="Boat Health Fisher",
        role="fisherman",
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
        registration_number="BH-001",
        fuel_capacity_liters=100.0,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


# ─────────────────────────────────────────────
# FUEL LOG TESTS
# ─────────────────────────────────────────────

def test_add_fuel_log_basic(db: Session, boat: Boat):
    """Fuel log is created and stored correctly."""
    payload = FuelLogCreate(
        boat_id=boat.id,
        fuel_level_start_percent=80.0,
        fuel_level_end_percent=60.0,
        distance_traveled_km=40.0,
    )
    log = BoatHealthService.create_fuel_log(db, payload)
    assert log.id is not None


def test_fuel_summary_no_warning(db: Session, boat: Boat):
    """No warnings when fuel is above threshold."""
    payload = FuelLogCreate(
        boat_id=boat.id,
        fuel_level_start_percent=90.0,
        fuel_level_end_percent=75.0,
        distance_traveled_km=30.0,
    )
    BoatHealthService.create_fuel_log(db, payload)
    summary = BoatHealthService.get_fuel_summary(db, boat.id)
    assert summary.current_fuel_percent == 75.0
    assert summary.total_fuel_logs >= 1


def test_fuel_summary_empty(db: Session, boat: Boat):
    """Summary on boat with no logs returns safe defaults."""
    summary = BoatHealthService.get_fuel_summary(db, boat.id)
    assert summary.total_fuel_logs == 0
    assert summary.current_fuel_percent is None
    assert summary.low_fuel_warning is False


# ─────────────────────────────────────────────
# MAINTENANCE TESTS
# ─────────────────────────────────────────────

def test_add_maintenance_scheduled(db: Session, boat: Boat):
    """Scheduled maintenance record is persisted."""
    future_date = datetime.utcnow() + timedelta(days=10)
    payload = MaintenanceCreate(
        boat_id=boat.id,
        maintenance_type="oil_change",
        description="Regular oil change",
        scheduled_date=future_date,
        cost_rupees=1500.0,
    )
    record = BoatHealthService.create_maintenance_record(db, payload)
    assert record.id is not None
    assert record.maintenance_type == "oil_change"
    assert record.completed_date is None


def test_maintenance_overdue_detection(db: Session, boat: Boat):
    """Overdue maintenance is flagged."""
    overdue_date = datetime.utcnow() - timedelta(days=45)
    payload = MaintenanceCreate(
        boat_id=boat.id,
        maintenance_type="engine_servicing",
        description="Overdue servicing",
        scheduled_date=overdue_date,
    )
    BoatHealthService.create_maintenance_record(db, payload)
    due = BoatHealthService.get_maintenance_due(db, boat.id)
    assert len(due.overdue_maintenance) >= 1


def test_maintenance_due_upcoming(db: Session, boat: Boat):
    """Upcoming maintenance appears in upcoming list."""
    upcoming_date = datetime.utcnow() + timedelta(days=15)
    payload = MaintenanceCreate(
        boat_id=boat.id,
        maintenance_type="filter_replacement",
        description="Filter replacement upcoming",
        scheduled_date=upcoming_date,
    )
    BoatHealthService.create_maintenance_record(db, payload)
    due = BoatHealthService.get_maintenance_due(db, boat.id)
    assert len(due.upcoming_maintenance) >= 1


# ─────────────────────────────────────────────
# HEALTH SCORE TESTS
# ─────────────────────────────────────────────

def test_health_score_no_data(db: Session, boat: Boat):
    """Health score on a new boat returns neutral/Good score."""
    score = BoatHealthService.calculate_health_score(db, boat.id)
    assert score.health_score >= 50
    assert score.boat_id == boat.id
    assert score.status in ("Good", "Warning", "Critical")


def test_health_score_critical_fuel(db: Session, boat: Boat):
    """Critical fuel drags score into Warning/Critical band."""
    payload = FuelLogCreate(
        boat_id=boat.id,
        fuel_level_start_percent=12.0,
        fuel_level_end_percent=5.0,
    )
    BoatHealthService.create_fuel_log(db, payload)
    score = BoatHealthService.calculate_health_score(db, boat.id)
    assert score.status in ("Warning", "Critical")


def test_health_score_overdue_maintenance(db: Session, boat: Boat):
    """Overdue maintenance triggers Warning or Critical status."""
    overdue_date = datetime.utcnow() - timedelta(days=60)
    BoatHealthService.create_maintenance_record(db, MaintenanceCreate(
        boat_id=boat.id,
        maintenance_type="engine_servicing",
        description="Overdue servicing",
        scheduled_date=overdue_date,
    ))
    score = BoatHealthService.calculate_health_score(db, boat.id)
    assert score.status in ("Warning", "Critical")
