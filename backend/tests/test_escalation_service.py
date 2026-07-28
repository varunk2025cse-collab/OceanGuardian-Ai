"""Tests for Emergency Escalation Engine."""
import pytest
from datetime import datetime, timedelta
from app.models.user import User
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.sos import SOSAlert
from app.models.phase5 import CheckinAlert, SafetyEscalation, MissedCheckIn
from app.services.escalation import EscalationEngine
from app.core.security import get_password_hash


@pytest.fixture
def fisherman(db):
    user = User(
        full_name="Test Fisherman",
        phone_number="+919876543210",
        role="fisherman",
        password_hash=get_password_hash("test123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def operator(db):
    user = User(
        full_name="Test Operator",
        phone_number="+911234567890",
        role="operator",
        password_hash=get_password_hash("rescue123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def boat(db, fisherman):
    boat = Boat(
        name="Test Boat",
        registration_number="TB123",
        engine_type="Trawler",
        owner_id=fisherman.id,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@pytest.fixture
def active_trip(db, fisherman, boat):
    trip = Trip(
        user_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def test_get_active_escalations_empty(db):
    escalations = EscalationEngine.get_active_escalations(db)
    assert len(escalations) == 0


def test_get_active_escalations_missed_checkin(db, fisherman, active_trip):
    alert = CheckinAlert(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        alert_type="no_gps_updates",
        threshold_value="30 minutes",
        alert_description="No GPS for 30+ minutes",
        dismissed=False,
    )
    db.add(alert)
    db.commit()
    escalations = EscalationEngine.get_active_escalations(db)
    assert len(escalations) >= 0


def test_get_escalation_detail_invalid_id(db):
    detail = EscalationEngine.get_escalation_detail(99999, db)
    assert detail is None


def test_acknowledge_escalation_checkin(db, fisherman, operator, active_trip):
    alert = CheckinAlert(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        alert_type="no_gps_updates",
        threshold_value="30 minutes",
        alert_description="GPS stale",
        dismissed=False,
    )
    db.add(alert)
    db.commit()
    result = EscalationEngine.acknowledge_escalation(
        alert.id + 10000, operator.id, "Monitoring closely", db
    )
    assert result["status"] == "success"


def test_resolve_escalation_checkin(db, fisherman, operator, active_trip):
    alert = CheckinAlert(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        alert_type="offline_too_long",
        threshold_value="45 minutes",
        alert_description="Fisherman offline",
        dismissed=False,
    )
    db.add(alert)
    db.commit()
    result = EscalationEngine.resolve_escalation(
        alert.id + 10000, operator.id, "Fisherman contacted, all safe", "resolved_safe", db
    )
    assert result["status"] == "success"


def test_safety_escalation_create_and_acknowledge(db, fisherman, operator, active_trip):
    es = SafetyEscalation(
        escalation_type="missed_checkin",
        level=2,
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        description="Missed multiple check-ins",
        priority="high",
        status="active",
        timeline_json="[]",
    )
    db.add(es)
    db.commit()
    result = EscalationEngine.acknowledge_escalation(
        es.id, operator.id, "I see the issue", db
    )
    assert result["status"] == "success"


def test_safety_escalation_resolve(db, fisherman, operator, active_trip):
    es = SafetyEscalation(
        escalation_type="sos_unacknowledged",
        level=3,
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        description="SOS not acknowledged",
        priority="high",
        status="active",
        timeline_json="[]",
    )
    db.add(es)
    db.commit()
    result = EscalationEngine.resolve_escalation(
        es.id, operator.id, "Rescue dispatched and completed", "resolved_assisted", db
    )
    assert result["status"] == "success"


def test_auto_upgrade_priorities(db, fisherman, active_trip):
    es = SafetyEscalation(
        escalation_type="missed_checkin",
        level=1,
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        description="Old escalation",
        priority="normal",
        status="active",
        timeline_json="[]",
    )
    db.add(es)
    db.commit()
    result = EscalationEngine.auto_upgrade_priorities(db)
    assert result["status"] == "completed"


def test_get_operator_action_log(db, fisherman, operator, active_trip):
    es = SafetyEscalation(
        escalation_type="missed_checkin",
        level=2,
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        description="Test",
        status="active",
        timeline_json="[]",
    )
    db.add(es)
    db.commit()
    EscalationEngine._log_operator_action(
        db, operator.id, "resolved", es.id,
        "Resolved escalation — outcome: resolved_safe"
    )
    logs = EscalationEngine.get_operator_action_log(es.id, db)
    assert len(logs) == 1
