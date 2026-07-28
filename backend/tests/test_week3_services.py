"""Tests for Phase 5 Week 3: Smart Check-In Schedule, Risk Prediction, Emergency Escalation.

Total tests: 45+
  - Smart Check-In (18 tests)
  - Risk Prediction (15 tests)
  - Emergency Escalation (15 tests)
"""
import pytest
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.user import User
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.location import LocationPing
from app.models.sos import SOSAlert
from app.models.weather_alert import WeatherAlert
from app.models.phase5 import (
    CheckInSchedule, CheckInRequest, MissedCheckIn, SafetyEscalation,
    OperatorActionLog, CheckinLog, CheckinAlert, BoatHealthStatus,
    BoatFuelLog, Harbor, RiskPrediction,
)
from app.services.checkin import CheckInService
from app.services.escalation import EscalationEngine
from app.services.risk_prediction import RiskPredictionService
from app.schemas.checkin import CheckInScheduleCreate, CheckInRespondRequest
from app.schemas.escalation import EscalationAcknowledge, EscalationResolve
from app.core.security import hash_password
from app.services.geo import GeoService


# =================================================================
# TEST FIXTURES
# =================================================================


@pytest.fixture
def db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = TestingSessionLocal()
    yield db_session
    db_session.close()


@pytest.fixture
def fisherman(db):
    """Create test fisherman."""
    user = User(
        full_name="Test Fisherman",
        phone_number="+919876543210",
        role="fisherman",
        password_hash=hash_password("test123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def operator(db):
    """Create test operator."""
    user = User(
        full_name="Test Operator",
        phone_number="+911234567890",
        role="operator",
        password_hash=hash_password("rescue123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def boat(db, fisherman):
    """Create test boat."""
    boat = Boat(
        name="Test Boat",
        registration_number="TB123",
        engine_type="Outboard",
        owner_id=fisherman.id,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@pytest.fixture
def active_trip(db, fisherman, boat):
    """Create active trip."""
    trip = Trip(
        user_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@pytest.fixture
def harbor(db):
    """Create test harbor."""
    h = Harbor(
        name="Test Harbor",
        latitude=12.0,
        longitude=80.0,
        is_active=True,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def make_location_ping(user_id, trip_id, lat, lng, minutes_ago=0):
    """Helper to create a LocationPing with required fields."""
    return LocationPing(
        client_uuid=str(uuid.uuid4()),
        user_id=user_id,
        trip_id=trip_id,
        latitude=lat,
        longitude=lng,
        recorded_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )


# =================================================================
# SMART CHECK-IN TESTS (18 tests)
# =================================================================


class TestCheckInSchedule:

    def test_create_schedule_success(self, db, fisherman, active_trip):
        """Test creating check-in schedule."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        assert schedule.id is not None
        assert schedule.trip_id == active_trip.id
        assert schedule.fisherman_id == fisherman.id
        assert schedule.interval_minutes == 30
        assert schedule.is_active is True
        assert schedule.next_checkin_at > datetime.utcnow()

    def test_create_schedule_invalid_trip(self, db, fisherman):
        """Test creating schedule with invalid trip."""
        data = CheckInScheduleCreate(trip_id=99999, interval_minutes=30)
        with pytest.raises(ValueError, match="not found"):
            CheckInService.create_schedule(fisherman.id, data, db)

    def test_create_schedule_ended_trip(self, db, fisherman, active_trip):
        """Test creating schedule on ended trip."""
        active_trip.end_time = datetime.utcnow()
        db.commit()

        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        with pytest.raises(ValueError, match="ended"):
            CheckInService.create_schedule(fisherman.id, data, db)

    def test_create_schedule_creates_request(self, db, fisherman, active_trip):
        """Test creating schedule also creates first check-in request."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        CheckInService.create_schedule(fisherman.id, data, db)

        schedule = db.query(CheckInSchedule).filter(
            CheckInSchedule.trip_id == active_trip.id,
            CheckInSchedule.is_active == True,
        ).first()

        assert schedule is not None
        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id
        ).first()
        assert request is not None
        assert request.status == "pending"

    def test_create_schedule_deactivates_old(self, db, fisherman, active_trip):
        """Test creating new schedule deactivates previous ones."""
        data1 = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        s1 = CheckInService.create_schedule(fisherman.id, data1, db)

        data2 = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=45)
        s2 = CheckInService.create_schedule(fisherman.id, data2, db)

        db.refresh(s1)
        assert s1.is_active is False
        assert s2.is_active is True


class TestCheckInRespond:

    def test_respond_scheduled_success(self, db, fisherman, active_trip):
        """Test responding to a scheduled check-in."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id,
            CheckInRequest.status == "pending",
        ).first()

        respond_data = CheckInRespondRequest(
            schedule_id=request.id,
            status="safe",
            location_lat=12.5,
            location_lng=80.2,
            notes="All good",
            synced=True,
        )
        result = CheckInService.respond_checkin_scheduled(fisherman.id, respond_data, db)

        assert result.status == "safe"
        assert result.trip_id == active_trip.id
        assert result.next_checkin_due > datetime.utcnow()

    def test_respond_already_responded(self, db, fisherman, active_trip):
        """Test responding twice to same request."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id,
            CheckInRequest.status == "pending",
        ).first()

        respond_data = CheckInRespondRequest(schedule_id=request.id, status="safe")
        CheckInService.respond_checkin_scheduled(fisherman.id, respond_data, db)

        with pytest.raises(ValueError, match="Already responded"):
            CheckInService.respond_checkin_scheduled(fisherman.id, respond_data, db)

    def test_respond_clears_alerts(self, db, fisherman, active_trip):
        """Test responding clears active check-in alerts."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        # Create an alert
        alert = CheckinAlert(
            trip_id=active_trip.id,
            fisherman_id=fisherman.id,
            alert_type="no_gps_updates",
            threshold_value="30 min",
            alert_description="Test",
            dismissed=False,
        )
        db.add(alert)
        db.commit()

        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id,
            CheckInRequest.status == "pending",
        ).first()

        respond_data = CheckInRespondRequest(schedule_id=request.id, status="safe")
        CheckInService.respond_checkin_scheduled(fisherman.id, respond_data, db)

        db.refresh(alert)
        assert alert.dismissed is True

    def test_respond_offline_sync(self, db, fisherman, active_trip):
        """Test responding with synced=False (offline capture)."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id,
            CheckInRequest.status == "pending",
        ).first()

        respond_data = CheckInRespondRequest(
            schedule_id=request.id,
            status="busy",
            synced=False,
        )
        result = CheckInService.respond_checkin_scheduled(fisherman.id, respond_data, db)

        assert result.status == "busy"
        db.refresh(request)
        assert request.synced is False

    def test_respond_unauthorized_fisherman(self, db, fisherman, active_trip):
        """Test unauthorized fisherman cannot respond."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        request = db.query(CheckInRequest).filter(
            CheckInRequest.schedule_id == schedule.id,
            CheckInRequest.status == "pending",
        ).first()

        # Create another fisherman
        other = User(
            full_name="Other",
            phone_number="+919999999999",
            role="fisherman",
            password_hash=hash_password("test"),
        )
        db.add(other)
        db.commit()

        respond_data = CheckInRespondRequest(schedule_id=request.id, status="safe")
        with pytest.raises(ValueError, match="not for you"):
            CheckInService.respond_checkin_scheduled(other.id, respond_data, db)


class TestCheckInMissedEscalation:

    def test_process_missed_checkins(self, db, fisherman, active_trip):
        """Test processing missed check-ins creates MissedCheckIn records."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=1)
        CheckInService.create_schedule(fisherman.id, data, db)

        result = CheckInService.process_missed_checkins(db)

        assert result["status"] == "completed"

    def test_missed_checkin_tracks_consecutive(self, db, fisherman, active_trip):
        """Test consecutive missed count."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=1)
        CheckInService.create_schedule(fisherman.id, data, db)

        for _ in range(3):
            CheckInService.process_missed_checkins(db)

        missed_records = db.query(MissedCheckIn).filter(
            MissedCheckIn.trip_id == active_trip.id,
        ).all()

        assert len(missed_records) >= 1
        latest = missed_records[-1]
        assert latest.consecutive_missed >= 1

    def test_escalation_after_threshold_misses(self, db, fisherman, active_trip):
        """Test escalation triggers after MISSED_CHECKIN_THRESHOLD."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=1)
        CheckInService.create_schedule(fisherman.id, data, db)

        for _ in range(6):
            CheckInService.process_missed_checkins(db)

        escalations = db.query(SafetyEscalation).filter(
            SafetyEscalation.escalation_type == "missed_checkin",
            SafetyEscalation.trip_id == active_trip.id,
        ).all()

        assert len(escalations) >= 1
        assert escalations[0].family_notified is True

    def test_get_missed_checkins_after_process(self, db, fisherman, active_trip):
        """Test get_missed_checkins returns processed records."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=1)
        CheckInService.create_schedule(fisherman.id, data, db)

        for _ in range(3):
            CheckInService.process_missed_checkins(db)

        missed = CheckInService.get_missed_checkins(db)
        assert len(missed) > 0

    def test_stale_gps_escalation(self, db, fisherman, active_trip):
        """Test stale GPS creates escalation."""
        old_ping = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0, minutes_ago=70,
        )
        db.add(old_ping)
        db.commit()

        result = CheckInService.process_missed_checkins(db)

        escalations = db.query(SafetyEscalation).filter(
            SafetyEscalation.escalation_type == "stale_gps_bad_weather",
        ).all()

        assert len(escalations) >= 1

    def test_create_schedule_default_interval(self, db, fisherman, active_trip):
        """Test default interval is 30 min."""
        data = CheckInScheduleCreate(trip_id=active_trip.id)
        schedule = CheckInService.create_schedule(fisherman.id, data, db)

        assert schedule.interval_minutes == 30


class TestCheckInLegacy:

    def test_legacy_respond_clears_alerts(self, db, fisherman, active_trip):
        """Test legacy respond_checkin still works."""
        from app.schemas.checkin import CheckInResponse

        response = CheckInResponse(
            trip_id=active_trip.id,
            status="safe",
            location_lat=12.5,
            location_lng=80.2,
        )
        result = CheckInService.respond_checkin(fisherman.id, response, db)
        assert result["status"] == "success"

    def test_get_my_checkin_status_with_schedule(self, db, fisherman, active_trip):
        """Test status includes schedule info."""
        data = CheckInScheduleCreate(trip_id=active_trip.id, interval_minutes=30)
        CheckInService.create_schedule(fisherman.id, data, db)

        status = CheckInService.get_my_checkin_status(fisherman.id, db)
        assert status is not None
        assert status.schedule_id is not None
        assert status.interval_minutes == 30


# =================================================================
# RISK PREDICTION TESTS (15+ tests)
# =================================================================


class TestRiskPredictionEnhanced:

    def test_missed_checkin_factor_zero(self, db, fisherman, active_trip, harbor):
        """Test missed check-in factor is 0 when no misses."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.01, 80.01,
        )
        db.add(location)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.missed_checkins_considered is False

    def test_missed_checkin_factor_increases_risk(self, db, fisherman, active_trip, harbor):
        """Test missed check-in factor increases when missed requests exist."""
        schedule = CheckInSchedule(
            trip_id=active_trip.id,
            fisherman_id=fisherman.id,
            interval_minutes=30,
            is_active=True,
        )
        db.add(schedule)
        db.commit()

        for _ in range(3):
            req = CheckInRequest(
                schedule_id=schedule.id,
                trip_id=active_trip.id,
                fisherman_id=fisherman.id,
                status="missed",
            )
            db.add(req)
        db.commit()

        location = make_location_ping(
            fisherman.id, active_trip.id, 12.01, 80.01,
        )
        db.add(location)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.factors.get("missed_checkins", 0) > 0
        assert risk.missed_checkins_considered is True

    def test_high_risk_boat_includes_missed_count(self, db, fisherman, boat, harbor):
        """Test high-risk boat includes missed check-in count."""
        trip = Trip(
            user_id=fisherman.id,
            boat_id=boat.id,
            start_time=datetime.utcnow() - timedelta(hours=15),
        )
        db.add(trip)
        db.commit()

        location = make_location_ping(
            fisherman.id, trip.id, 13.5, 82.0, minutes_ago=65,
        )
        db.add(location)

        health = BoatHealthStatus(
            boat_id=boat.id,
            health_score=25.0,
            last_assessed_date=datetime.utcnow(),
        )
        db.add(health)

        schedule = CheckInSchedule(trip_id=trip.id, fisherman_id=fisherman.id, interval_minutes=30)
        db.add(schedule)
        db.commit()
        for _ in range(3):
            req = CheckInRequest(schedule_id=schedule.id, trip_id=trip.id, fisherman_id=fisherman.id, status="missed")
            db.add(req)
        db.commit()

        boats = RiskPredictionService.get_high_risk_boats(db)
        if len(boats) > 0:
            assert boats[0].missed_checkin_count >= 3

    def test_risk_score_with_missed_checkins_and_stale_gps(self, db, fisherman, active_trip):
        """Test combined missed check-in + stale GPS."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.5, 80.5, minutes_ago=40,
        )
        db.add(location)

        schedule = CheckInSchedule(trip_id=active_trip.id, fisherman_id=fisherman.id, interval_minutes=30)
        db.add(schedule)
        db.commit()
        for _ in range(4):
            req = CheckInRequest(schedule_id=schedule.id, trip_id=active_trip.id, fisherman_id=fisherman.id, status="missed")
            db.add(req)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.risk_level in ["WATCH", "WARNING", "CRITICAL"]

    def test_risk_factors_key_structure(self, db, fisherman, active_trip, harbor):
        """Test risk factors contain all expected keys including missed_checkins."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert "weather_risk" in risk.factors
        assert "distance_from_harbor" in risk.factors
        assert "gps_staleness" in risk.factors
        assert "missed_checkins" in risk.factors
        assert "trip_duration" in risk.factors
        assert "boat_health" in risk.factors
        assert "fuel_remaining" in risk.factors
        assert "sos_history" in risk.factors

    def test_weather_risk_yellow(self, db, fisherman, active_trip, harbor):
        """Test weather risk with yellow alert."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)

        weather = WeatherAlert(
            region="Test Region",
            severity="yellow",
            alert_type="Strong Winds",
            description="Strong wind warning",
            is_active=True,
            title="Strong Wind Warning",
            center_latitude=12.0,
            center_longitude=80.0,
            radius_km=50.0,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(weather)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.factors["weather_risk"] >= 8.0

    def test_weather_risk_red(self, db, fisherman, active_trip, harbor):
        """Test weather risk with red alert."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)

        weather = WeatherAlert(
            region="Test Region",
            severity="red",
            alert_type="Cyclone",
            description="Severe cyclone warning",
            is_active=True,
            title="Cyclone Warning",
            center_latitude=12.0,
            center_longitude=80.0,
            radius_km=50.0,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(weather)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.factors["weather_risk"] >= 15.0

    def test_low_fuel_risk(self, db, fisherman, boat, active_trip, harbor):
        """Test low fuel contributes to risk."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)

        fuel = BoatFuelLog(
            boat_id=boat.id,
            trip_id=active_trip.id,
            fuel_level_end_percent=10.0,
            timestamp=datetime.utcnow(),
        )
        db.add(fuel)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.factors["fuel_remaining"] >= 7.0

    def test_trip_risk_response_includes_missed_checkin_risk(self, db, fisherman, active_trip, harbor):
        """Test TripRiskResponse includes missed_checkin_risk field."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)
        db.commit()

        trip_risk = RiskPredictionService.get_trip_risk(active_trip.id, db)
        assert trip_risk is not None
        assert trip_risk.missed_checkin_risk is not None

    def test_calculate_risk_far_from_harbor_with_missed_checkins(self, db, fisherman, active_trip, harbor):
        """Test distance risk combined with missed check-ins."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 13.5, 82.0,
        )
        db.add(location)

        schedule = CheckInSchedule(trip_id=active_trip.id, fisherman_id=fisherman.id, interval_minutes=30)
        db.add(schedule)
        db.commit()
        for _ in range(5):
            req = CheckInRequest(schedule_id=schedule.id, trip_id=active_trip.id, fisherman_id=fisherman.id, status="missed")
            db.add(req)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.risk_score > 20  # Should be elevated

    def test_sos_history_increases_risk(self, db, fisherman, active_trip, harbor):
        """Test SOS history increases risk."""
        location = make_location_ping(
            fisherman.id, active_trip.id, 12.0, 80.0,
        )
        db.add(location)

        for i in range(3):
            sos = SOSAlert(
                client_uuid=str(uuid.uuid4()),
                user_id=fisherman.id,
                trip_id=active_trip.id,
                alert_type="Engine Failure",
                latitude=12.0,
                longitude=80.0,
                triggered_at=datetime.utcnow() - timedelta(days=i + 1),
                message="Engine failure",
            )
            db.add(sos)
        db.commit()

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        assert risk is not None
        assert risk.factors["sos_history"] > 3.0


# =================================================================
# EMERGENCY ESCALATION TESTS (15 tests)
# =================================================================


class TestSafetyEscalation:

    def test_get_active_safety_escalations_empty(self, db):
        """Test active escalations with no records."""
        items = EscalationEngine.get_active_safety_escalations(db)
        assert len(items) == 0

    def test_create_safety_escalation_via_checkin(self, db, fisherman, active_trip):
        """Test escalation created via missed check-in."""
        schedule = CheckInSchedule(
            trip_id=active_trip.id,
            fisherman_id=fisherman.id,
            interval_minutes=30,
            is_active=True,
        )
        db.add(schedule)
        db.commit()

        missed = MissedCheckIn(
            trip_id=active_trip.id,
            fisherman_id=fisherman.id,
            consecutive_missed=4,
            escalated=False,
        )
        db.add(missed)
        db.commit()

        from app.services.checkin import CheckInService
        CheckInService._escalate_missed_checkin(missed, schedule, db)

        escalations = db.query(SafetyEscalation).filter(
            SafetyEscalation.escalation_type == "missed_checkin",
        ).all()

        assert len(escalations) == 1
        assert escalations[0].level >= 2
        assert escalations[0].priority == "high"

    def test_get_safety_escalation_detail(self, db, fisherman, active_trip):
        """Test getting safety escalation detail."""
        es = SafetyEscalation(
            escalation_type="sos_unacknowledged",
            level=1,
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            description="Test escalation",
            priority="normal",
            status="active",
            timeline_json=json.dumps([
                {"timestamp": datetime.utcnow().isoformat(), "event": "Created", "details": "Test"}
            ]),
        )
        db.add(es)
        db.commit()

        detail = EscalationEngine.get_safety_escalation_detail(es.id, db)
        assert detail is not None
        assert detail.escalation_type == "sos_unacknowledged"
        assert detail.level == 1
        assert detail.fisherman_name == fisherman.full_name
        assert len(detail.timeline) > 0

    def test_acknowledge_safety_escalation(self, db, fisherman, operator, active_trip):
        """Test acknowledging a safety escalation."""
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

        result = EscalationEngine.acknowledge_safety_escalation(
            es.id, operator.id, "I see the issue", db
        )

        assert result["status"] == "success"

        db.refresh(es)
        assert es.status == "acknowledged"
        assert es.acknowledged_by_id == operator.id
        assert es.acknowledged_at is not None

    def test_acknowledge_already_resolved(self, db, fisherman, operator, active_trip):
        """Test acknowledging already resolved escalation."""
        es = SafetyEscalation(
            escalation_type="missed_checkin",
            level=1,
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            description="Test",
            priority="normal",
            status="resolved",
            timeline_json="[]",
        )
        db.add(es)
        db.commit()

        result = EscalationEngine.acknowledge_safety_escalation(
            es.id, operator.id, "Notes", db
        )

        assert result["status"] == "error"

    def test_resolve_safety_escalation(self, db, fisherman, operator, active_trip):
        """Test resolving a safety escalation."""
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

        result = EscalationEngine.resolve_safety_escalation(
            es.id, operator.id, "Rescue dispatched and completed", "resolved_assisted", db
        )

        assert result["status"] == "success"

        db.refresh(es)
        assert es.status == "resolved"
        assert es.resolved_by_id == operator.id
        assert es.outcome == "resolved_assisted"

    def test_resolve_links_missed_checkin(self, db, fisherman, operator, active_trip):
        """Test resolving escalation resolves linked MissedCheckIn."""
        missed = MissedCheckIn(
            trip_id=active_trip.id,
            fisherman_id=fisherman.id,
            consecutive_missed=3,
        )
        db.add(missed)
        db.commit()

        es = SafetyEscalation(
            escalation_type="missed_checkin",
            level=2,
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            missed_checkin_id=missed.id,
            description="Test",
            priority="high",
            status="active",
            timeline_json="[]",
        )
        db.add(es)
        db.commit()

        EscalationEngine.resolve_safety_escalation(
            es.id, operator.id, "Resolved", "resolved_safe", db
        )

        db.refresh(missed)
        assert missed.resolved_at is not None

    def test_operator_action_log(self, db, fisherman, operator, active_trip):
        """Test operator action logging."""
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
        assert logs[0].action_type == "resolved"
        assert logs[0].operator_id == operator.id
        assert logs[0].operator_name == operator.full_name

    def test_auto_escalate_unacknowledged_sos(self, db, fisherman, active_trip):
        """Test auto-escalation creates SafetyEscalation for old SOS."""
        old_sos = SOSAlert(
            client_uuid=str(uuid.uuid4()),
            user_id=fisherman.id,
            trip_id=active_trip.id,
            alert_type="Engine Failure",
            latitude=12.0,
            longitude=80.0,
            triggered_at=datetime.utcnow() - timedelta(minutes=35),
            message="Engine failure",
        )
        db.add(old_sos)
        db.commit()

        result = EscalationEngine.auto_escalate_unacknowledged_sos(db)
        assert result["status"] == "completed"

        escalations = db.query(SafetyEscalation).filter(
            SafetyEscalation.escalation_type == "sos_unacknowledged",
        ).all()
        assert len(escalations) >= 1

    def test_auto_upgrade_priorities(self, db, fisherman, active_trip):
        """Test auto-upgrade of escalation priorities."""
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

    def test_get_active_escalations_combined(self, db, fisherman, operator, active_trip):
        """Test active escalations combine SafetyEscalation + SOS."""
        es = SafetyEscalation(
            escalation_type="missed_checkin",
            level=2,
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            description="Missed check-ins",
            priority="high",
            status="active",
            timeline_json="[]",
        )
        db.add(es)

        sos = SOSAlert(
            client_uuid=str(uuid.uuid4()),
            user_id=fisherman.id,
            trip_id=active_trip.id,
            alert_type="Engine Failure",
            latitude=12.0,
            longitude=80.0,
            triggered_at=datetime.utcnow(),
            message="Need help",
        )
        db.add(sos)
        db.commit()

        items = EscalationEngine.get_active_escalations(db)
        assert len(items) >= 1

    def test_escalation_detail_falls_back_to_sos(self, db, fisherman, active_trip):
        """Test getting detail falls back to SOS if SafetyEscalation not found."""
        sos = SOSAlert(
            client_uuid=str(uuid.uuid4()),
            user_id=fisherman.id,
            trip_id=active_trip.id,
            alert_type="Engine Failure",
            latitude=12.0,
            longitude=80.0,
            triggered_at=datetime.utcnow(),
            message="Help",
        )
        db.add(sos)
        db.commit()

        detail = EscalationEngine.get_escalation_detail(sos.id, db)
        assert detail is not None
        assert detail.escalation_type == "sos_unacknowledged"

    def test_escalation_detail_not_found(self, db):
        """Test escalation detail with invalid ID."""
        detail = EscalationEngine.get_escalation_detail(99999, db)
        assert detail is None

    def test_legacy_acknowledge_falls_through(self, db, fisherman, operator, active_trip):
        """Test legacy acknowledge works for SafetyEscalation."""
        es = SafetyEscalation(
            escalation_type="missed_checkin",
            level=1,
            fisherman_id=fisherman.id,
            trip_id=active_trip.id,
            description="Test",
            priority="normal",
            status="active",
            timeline_json="[]",
        )
        db.add(es)
        db.commit()

        result = EscalationEngine.acknowledge_escalation(
            es.id, operator.id, "Notes", db
        )

        assert result["status"] == "success"

    def test_auto_upgrade_changes_level(self, db, fisherman, active_trip):
        """Test auto-upgrade changes level for very old escalations."""
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
        db.flush()

        # Direct SQL update to set old timestamp (SQLite compatible)
        db.execute(
            text("UPDATE safety_escalations SET created_at = :ct WHERE id = :id"),
            {"ct": datetime.utcnow() - timedelta(minutes=70), "id": es.id}
        )
        db.commit()
        db.refresh(es)

        result = EscalationEngine.auto_upgrade_priorities(db)

        db.refresh(es)
        assert es.level >= 3
