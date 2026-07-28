"""Tests for Smart Check-In System."""
import pytest
from datetime import datetime, timedelta
from app.models.user import User
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.location import LocationPing
from app.models.phase5 import CheckinLog, CheckinAlert
from app.services.checkin import CheckInService
from app.schemas.checkin import CheckInResponse
from app.core.security import get_password_hash


@pytest.fixture
def fisherman(db):
    """Create test fisherman."""
    user = User(
        name="Test Fisherman",
        phone_number="+919876543210",
        role="fisherman",
        password_hash=get_password_hash("test123"),
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
        type="Trawler",
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
        fisherman_id=fisherman.id,
        boat_id=boat.id,
        start_time=datetime.utcnow(),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def test_get_checkin_status_no_active_trip(db, fisherman):
    """Test get check-in status with no active trip."""
    status = CheckInService.get_my_checkin_status(fisherman.id, db)
    assert status is None


def test_get_checkin_status_creates_initial_log(db, fisherman, active_trip):
    """Test that checking status creates initial log."""
    status = CheckInService.get_my_checkin_status(fisherman.id, db)
    
    assert status is not None
    assert status.trip_id == active_trip.id
    assert status.fisherman_id == fisherman.id
    assert status.missed_count == 0
    assert status.status == "active"


def test_respond_checkin_success(db, fisherman, active_trip):
    """Test successful check-in response."""
    response = CheckInResponse(
        trip_id=active_trip.id,
        status="safe",
        location_lat=12.5,
        location_lng=80.2,
        notes="All good",
    )
    
    result = CheckInService.respond_checkin(fisherman.id, response, db)
    
    assert result["status"] == "success"
    assert "next_checkin_due" in result


def test_respond_checkin_records_location(db, fisherman, active_trip):
    """Test that check-in records location."""
    response = CheckInResponse(
        trip_id=active_trip.id,
        status="safe",
        location_lat=12.5,
        location_lng=80.2,
    )
    
    CheckInService.respond_checkin(fisherman.id, response, db)
    
    location = db.query(LocationPing).filter(
        LocationPing.trip_id == active_trip.id
    ).first()
    
    assert location is not None
    assert location.latitude == 12.5
    assert location.longitude == 80.2


def test_respond_checkin_invalid_trip(db, fisherman):
    """Test check-in with invalid trip ID."""
    response = CheckInResponse(
        trip_id=99999,
        status="safe",
    )
    
    with pytest.raises(ValueError, match="Invalid trip"):
        CheckInService.respond_checkin(fisherman.id, response, db)


def test_respond_checkin_ended_trip(db, fisherman, active_trip):
    """Test check-in on ended trip."""
    active_trip.end_time = datetime.utcnow()
    db.commit()
    
    response = CheckInResponse(
        trip_id=active_trip.id,
        status="safe",
    )
    
    with pytest.raises(ValueError, match="already ended"):
        CheckInService.respond_checkin(fisherman.id, response, db)


def test_respond_checkin_clears_alerts(db, fisherman, active_trip):
    """Test that check-in clears active alerts."""
    # Create alert
    alert = CheckinAlert(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        alert_type="no_gps_updates",
        threshold_value="30 minutes",
        alert_description="Test alert",
        dismissed=False,
    )
    db.add(alert)
    db.commit()
    
    response = CheckInResponse(
        trip_id=active_trip.id,
        status="safe",
    )
    
    CheckInService.respond_checkin(fisherman.id, response, db)
    
    db.refresh(alert)
    assert alert.dismissed is True
    assert alert.resolved_at is not None


def test_get_missed_checkins_empty(db):
    """Test get missed check-ins with no trips."""
    missed = CheckInService.get_missed_checkins(db)
    assert len(missed) == 0


def test_get_missed_checkins_with_stale_gps(db, fisherman, active_trip):
    """Test missed check-ins detection with stale GPS."""
    # Create old location ping
    old_ping = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=45),
    )
    db.add(old_ping)
    
    # Create old check-in log
    old_log = CheckinLog(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        last_update_time=datetime.utcnow() - timedelta(minutes=45),
        status="active",
        check_status="ok",
    )
    db.add(old_log)
    db.commit()
    
    missed = CheckInService.get_missed_checkins(db)
    
    assert len(missed) == 1
    assert missed[0].trip_id == active_trip.id
    assert missed[0].missed_count >= 1


def test_create_alert(db, fisherman, active_trip):
    """Test creating check-in alert."""
    alert = CheckInService.create_alert(
        trip_id=active_trip.id,
        fisherman_id=fisherman.id,
        alert_type="no_gps_updates",
        threshold_value="30 minutes",
        description="GPS stale for 30+ minutes",
        db=db,
    )
    
    assert alert.id is not None
    assert alert.trip_id == active_trip.id
    assert alert.alert_type == "no_gps_updates"
    assert alert.dismissed is False


def test_monitor_active_trips_no_alerts(db, fisherman, active_trip):
    """Test monitoring with recent GPS."""
    # Create recent location
    recent_ping = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=5),
    )
    db.add(recent_ping)
    db.commit()
    
    result = CheckInService.monitor_active_trips(db)
    
    assert result["status"] == "completed"
    assert result["alerts_created"] == 0


def test_monitor_active_trips_creates_stale_gps_alert(db, fisherman, active_trip):
    """Test monitoring creates alert for stale GPS."""
    # Create old location
    old_ping = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=35),
    )
    db.add(old_ping)
    db.commit()
    
    result = CheckInService.monitor_active_trips(db)
    
    assert result["alerts_created"] >= 1
    
    alert = db.query(CheckinAlert).filter(
        CheckinAlert.trip_id == active_trip.id,
        CheckinAlert.alert_type == "no_gps_updates",
    ).first()
    
    assert alert is not None


def test_monitor_active_trips_creates_offline_alert(db, fisherman, active_trip):
    """Test monitoring creates alert for offline too long."""
    # Create very old location
    old_ping = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=50),
    )
    db.add(old_ping)
    db.commit()
    
    result = CheckInService.monitor_active_trips(db)
    
    assert result["alerts_created"] >= 1
    
    alert = db.query(CheckinAlert).filter(
        CheckinAlert.trip_id == active_trip.id,
        CheckinAlert.alert_type == "offline_too_long",
    ).first()
    
    assert alert is not None


def test_monitor_doesnt_duplicate_alerts(db, fisherman, active_trip):
    """Test monitoring doesn't create duplicate alerts."""
    # Create old location
    old_ping = LocationPing(
        fisherman_id=fisherman.id,
        trip_id=active_trip.id,
        latitude=12.0,
        longitude=80.0,
        timestamp=datetime.utcnow() - timedelta(minutes=35),
    )
    db.add(old_ping)
    db.commit()
    
    # Run twice
    result1 = CheckInService.monitor_active_trips(db)
    result2 = CheckInService.monitor_active_trips(db)
    
    assert result1["alerts_created"] >= 1
    assert result2["alerts_created"] == 0  # No new alerts


def test_missed_checkins_sorted_by_count(db, fisherman, boat):
    """Test missed check-ins are sorted by severity."""
    # Create two trips with different staleness
    trip1 = Trip(fisherman_id=fisherman.id, boat_id=boat.id, start_time=datetime.utcnow())
    trip2 = Trip(fisherman_id=fisherman.id, boat_id=boat.id, start_time=datetime.utcnow())
    db.add_all([trip1, trip2])
    db.commit()
    
    # Trip 1: very stale (60 min)
    log1 = CheckinLog(
        trip_id=trip1.id,
        fisherman_id=fisherman.id,
        last_update_time=datetime.utcnow() - timedelta(minutes=60),
        status="alert",
        check_status="stale",
    )
    
    # Trip 2: moderately stale (35 min)
    log2 = CheckinLog(
        trip_id=trip2.id,
        fisherman_id=fisherman.id,
        last_update_time=datetime.utcnow() - timedelta(minutes=35),
        status="warning",
        check_status="stale",
    )
    
    db.add_all([log1, log2])
    db.commit()
    
    missed = CheckInService.get_missed_checkins(db)
    
    assert len(missed) == 2
    # Most severe first
    assert missed[0].missed_count > missed[1].missed_count
