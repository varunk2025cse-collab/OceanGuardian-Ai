"""Tests for Phase 5 Week 2: Fuel & Boat Health, Family Portal, Analytics."""
import pytest
from datetime import datetime, timedelta
from app.models.phase5 import (
    BoatFuelLog,
    BoatMaintenance,
    BoatHealthStatus,
    FamilyPortalAccess,
    FamilySafetyEvent,
)
from app.models.boat import Boat
from app.models.trip import Trip
from app.models.user import User
from app.models.sos import SOSAlert
from app.services.boat_health import (
    BoatHealthService,
    FuelLogCreate,
    MaintenanceCreate,
)
from app.services.family_portal import FamilySafetyPortalService
from app.services.analytics import AnalyticsService
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base


@pytest.fixture
def db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_fisherman(db: Session):
    """Create test fisherman."""
    user = User(
        phone_number="+911234567890",
        name="Test Fisherman",
        role="fisherman",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_family(db: Session):
    """Create test family member."""
    user = User(
        phone_number="+919876543210",
        name="Test Family",
        role="family",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_operator(db: Session):
    """Create test operator."""
    user = User(
        phone_number="+918888888888",
        name="Test Operator",
        role="operator",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_boat(db: Session, test_fisherman: User):
    """Create test boat."""
    boat = Boat(
        fisherman_id=test_fisherman.id,
        boat_name="Test Boat",
        boat_type="Fishing",
        registration_number="TN-001",
        fuel_capacity_liters=500,
        length_meters=10,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@pytest.fixture
def test_trip(db: Session, test_fisherman: User, test_boat: Boat):
    """Create test trip."""
    trip = Trip(
        fisherman_id=test_fisherman.id,
        boat_id=test_boat.id,
        start_time=datetime.utcnow(),
        departure_harbor_id=None,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


# =================================================================
# FUEL & BOAT HEALTH TESTS (15 tests)
# =================================================================


def test_create_fuel_log(db: Session, test_boat: Boat, test_trip: Trip):
    """Test creating fuel log entry."""
    fuel_data = FuelLogCreate(
        boat_id=test_boat.id,
        trip_id=test_trip.id,
        fuel_level_start_percent=100,
        fuel_level_end_percent=75,
        fuel_consumed_liters=50,
        distance_traveled_km=100,
    )

    log = BoatHealthService.create_fuel_log(db, fuel_data)

    assert log.boat_id == test_boat.id
    assert log.trip_id == test_trip.id
    assert log.fuel_level_start_percent == 100
    assert log.fuel_level_end_percent == 75
    assert log.efficiency_km_per_liter == 2.0


def test_fuel_log_efficiency_calculation(db: Session, test_boat: Boat):
    """Test fuel efficiency calculation."""
    fuel_data = FuelLogCreate(
        boat_id=test_boat.id,
        fuel_level_start_percent=100,
        fuel_level_end_percent=50,
        fuel_consumed_liters=100,
        distance_traveled_km=300,
    )

    log = BoatHealthService.create_fuel_log(db, fuel_data)

    assert log.efficiency_km_per_liter == 3.0


def test_get_fuel_summary(db: Session, test_boat: Boat):
    """Test getting fuel summary."""
    # Create multiple fuel logs
    for i in range(3):
        fuel_data = FuelLogCreate(
            boat_id=test_boat.id,
            fuel_level_start_percent=100 - (i * 10),
            fuel_level_end_percent=90 - (i * 10),
            fuel_consumed_liters=50,
            distance_traveled_km=100,
        )
        BoatHealthService.create_fuel_log(db, fuel_data)

    summary = BoatHealthService.get_fuel_summary(db, test_boat.id)

    assert summary.boat_id == test_boat.id
    assert summary.total_fuel_logs == 3
    assert summary.current_fuel_percent == 70  # Last log


def test_fuel_summary_low_fuel_warning(db: Session, test_boat: Boat):
    """Test low fuel warning."""
    fuel_data = FuelLogCreate(
        boat_id=test_boat.id,
        fuel_level_start_percent=50,
        fuel_level_end_percent=15,
        fuel_consumed_liters=100,
        distance_traveled_km=100,
    )
    BoatHealthService.create_fuel_log(db, fuel_data)

    summary = BoatHealthService.get_fuel_summary(db, test_boat.id)

    assert summary.low_fuel_warning is True
    assert summary.current_fuel_percent == 15


def test_create_maintenance_record(db: Session, test_boat: Boat):
    """Test creating maintenance record."""
    scheduled_date = datetime.utcnow() + timedelta(days=30)
    maint_data = MaintenanceCreate(
        boat_id=test_boat.id,
        maintenance_type="oil_change",
        description="Regular oil change",
        scheduled_date=scheduled_date,
        cost_rupees=5000,
        technician_name="John",
        service_center="Main Harbor",
    )

    record = BoatHealthService.create_maintenance_record(db, maint_data)

    assert record.boat_id == test_boat.id
    assert record.maintenance_type == "oil_change"
    assert record.cost_rupees == 5000


def test_get_maintenance_due(db: Session, test_boat: Boat):
    """Test getting maintenance due."""
    now = datetime.utcnow()
    
    # Create overdue maintenance
    overdue_data = MaintenanceCreate(
        boat_id=test_boat.id,
        maintenance_type="engine_servicing",
        description="Engine service overdue",
        scheduled_date=now - timedelta(days=10),
        cost_rupees=10000,
        technician_name="John",
        service_center="Harbor",
    )
    BoatHealthService.create_maintenance_record(db, overdue_data)

    # Create upcoming maintenance
    upcoming_data = MaintenanceCreate(
        boat_id=test_boat.id,
        maintenance_type="filter_replacement",
        description="Filter replacement upcoming",
        scheduled_date=now + timedelta(days=5),
        cost_rupees=2000,
        technician_name="Jane",
        service_center="Harbor",
    )
    BoatHealthService.create_maintenance_record(db, upcoming_data)

    due = BoatHealthService.get_maintenance_due(db, test_boat.id)

    assert len(due.overdue_maintenance) == 1
    assert len(due.upcoming_maintenance) == 1
    assert len(due.critical_issues) > 0


def test_calculate_health_score_good(db: Session, test_boat: Boat):
    """Test health score calculation - good status."""
    # Add good fuel data
    fuel_data = FuelLogCreate(
        boat_id=test_boat.id,
        fuel_level_start_percent=100,
        fuel_level_end_percent=80,
        fuel_consumed_liters=50,
        distance_traveled_km=100,
    )
    BoatHealthService.create_fuel_log(db, fuel_data)

    # Update health status with low engine hours
    BoatHealthService.update_health_status(db, test_boat.id, engine_hours=1000)

    health = BoatHealthService.calculate_health_score(db, test_boat.id)

    assert health.boat_id == test_boat.id
    assert health.health_score >= 70
    assert health.status == "Good"
    assert health.risk_level == "Low"


def test_calculate_health_score_warning(db: Session, test_boat: Boat):
    """Test health score calculation - warning status."""
    # Create overdue maintenance
    maint_data = MaintenanceCreate(
        boat_id=test_boat.id,
        maintenance_type="engine_servicing",
        description="Overdue servicing",
        scheduled_date=datetime.utcnow() - timedelta(days=30),
        cost_rupees=10000,
        technician_name="John",
        service_center="Harbor",
    )
    BoatHealthService.create_maintenance_record(db, maint_data)

    health = BoatHealthService.calculate_health_score(db, test_boat.id)

    assert 40 <= health.health_score < 70
    assert health.status == "Warning"
    assert health.risk_level == "Medium"


def test_calculate_health_score_critical(db: Session, test_boat: Boat):
    """Test health score calculation - critical status."""
    # Create multiple overdue maintenance
    for i in range(3):
        maint_data = MaintenanceCreate(
            boat_id=test_boat.id,
            maintenance_type="engine_servicing",
            description=f"Overdue servicing {i}",
            scheduled_date=datetime.utcnow() - timedelta(days=60 + i*20),
            cost_rupees=10000,
            technician_name="John",
            service_center="Harbor",
        )
        BoatHealthService.create_maintenance_record(db, maint_data)

    health = BoatHealthService.calculate_health_score(db, test_boat.id)

    assert health.health_score < 40
    assert health.status == "Critical"
    assert health.risk_level == "High"


def test_update_engine_hours(db: Session, test_boat: Boat):
    """Test updating engine hours."""
    status = BoatHealthService.update_health_status(db, test_boat.id, engine_hours=5000)

    assert status.boat_id == test_boat.id
    assert status.engine_hours == 5000


def test_fuel_summary_no_logs(db: Session, test_boat: Boat):
    """Test fuel summary with no logs."""
    summary = BoatHealthService.get_fuel_summary(db, test_boat.id)

    assert summary.boat_id == test_boat.id
    assert summary.current_fuel_percent is None
    assert summary.total_fuel_logs == 0


def test_maintenance_due_empty(db: Session, test_boat: Boat):
    """Test maintenance due with no records."""
    due = BoatHealthService.get_maintenance_due(db, test_boat.id)

    assert due.boat_id == test_boat.id
    assert len(due.overdue_maintenance) == 0
    assert len(due.upcoming_maintenance) == 0


def test_health_score_invalid_boat(db: Session):
    """Test health score with invalid boat."""
    with pytest.raises(ValueError):
        BoatHealthService.calculate_health_score(db, 99999)


# =================================================================
# FAMILY SAFETY PORTAL TESTS (12 tests)
# =================================================================


def test_family_portal_access_granted(db: Session, test_family: User, test_fisherman: User):
    """Test family portal access granted."""
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="view_only",
        can_view_live_location=True,
        can_view_trip_history=True,
        can_receive_alerts=True,
    )
    db.add(access)
    db.commit()

    status = FamilySafetyPortalService.get_fisherman_safety_status(
        db, test_fisherman.id, test_family.id
    )

    assert status.fisherman_id == test_fisherman.id
    assert status.current_status == "unknown"


def test_family_portal_access_denied(db: Session, test_family: User, test_fisherman: User):
    """Test family portal access denied."""
    with pytest.raises(PermissionError):
        FamilySafetyPortalService.get_fisherman_safety_status(
            db, test_fisherman.id, test_family.id
        )


def test_get_safety_status_at_sea(
    db: Session, test_family: User, test_fisherman: User, test_trip: Trip
):
    """Test safety status when fisherman at sea."""
    # Grant access
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
        can_view_live_location=True,
    )
    db.add(access)
    db.commit()

    status = FamilySafetyPortalService.get_fisherman_safety_status(
        db, test_fisherman.id, test_family.id
    )

    assert status.current_status == "at_sea"
    assert status.trip_status == "active"


def test_get_safety_timeline(
    db: Session, test_family: User, test_fisherman: User
):
    """Test getting safety timeline."""
    # Grant access
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
    )
    db.add(access)
    db.commit()

    # Create safety event
    event = FamilySafetyPortalService.create_safety_event(
        db,
        test_family.id,
        test_fisherman.id,
        "trip_started",
        "Fisherman started a trip",
        "info",
    )

    timeline = FamilySafetyPortalService.get_safety_timeline(
        db, test_fisherman.id, test_family.id
    )

    assert len(timeline.events) >= 1
    assert timeline.total_events >= 1


def test_get_family_dashboard_single_fisherman(
    db: Session, test_family: User, test_fisherman: User
):
    """Test family dashboard with single linked fisherman."""
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
        can_view_live_location=True,
    )
    db.add(access)
    db.commit()

    dashboard = FamilySafetyPortalService.get_family_dashboard(db, test_family.id)

    assert len(dashboard.linked_fishermen) == 1
    assert dashboard.linked_fishermen[0]["id"] == test_fisherman.id


def test_create_safety_event(db: Session, test_family: User, test_fisherman: User):
    """Test creating safety event."""
    event = FamilySafetyPortalService.create_safety_event(
        db,
        test_family.id,
        test_fisherman.id,
        "sos_alert",
        "Emergency alert received",
        "critical",
    )

    assert event.family_member_id == test_family.id
    assert event.fisherman_id == test_fisherman.id
    assert event.event_type == "sos_alert"
    assert event.severity == "critical"


def test_connection_lost_warning(
    db: Session, test_family: User, test_fisherman: User
):
    """Test connection lost warning."""
    from app.models.location import LocationPing

    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
        can_view_live_location=True,
    )
    db.add(access)

    # Create old location (40 minutes ago)
    old_time = datetime.utcnow() - timedelta(minutes=40)
    location = LocationPing(
        fisherman_id=test_fisherman.id,
        latitude=13.0,
        longitude=80.0,
        accuracy_meters=10,
        timestamp=old_time,
        synced_at=old_time,
    )
    db.add(location)
    db.commit()

    status = FamilySafetyPortalService.get_fisherman_safety_status(
        db, test_fisherman.id, test_family.id
    )

    assert status.connection_lost_warning is True
    assert status.last_update_minutes_ago >= 40


def test_active_sos_in_status(
    db: Session, test_family: User, test_fisherman: User
):
    """Test active SOS shown in safety status."""
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
    )
    db.add(access)

    # Create active SOS
    sos = SOSAlert(
        fisherman_id=test_fisherman.id,
        alert_type="engine_failure",
        latitude=13.0,
        longitude=80.0,
        created_at=datetime.utcnow(),
    )
    db.add(sos)
    db.commit()

    status = FamilySafetyPortalService.get_fisherman_safety_status(
        db, test_fisherman.id, test_family.id
    )

    assert status.active_sos is True
    assert status.sos_details is not None


def test_dashboard_no_fishermen(db: Session, test_family: User):
    """Test dashboard with no linked fishermen."""
    dashboard = FamilySafetyPortalService.get_family_dashboard(db, test_family.id)

    assert len(dashboard.linked_fishermen) == 0
    assert dashboard.active_alerts == 0


def test_dashboard_active_alerts_count(
    db: Session, test_family: User, test_fisherman: User
):
    """Test active alerts count in dashboard."""
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
    )
    db.add(access)

    # Create multiple SOS alerts
    for i in range(2):
        sos = SOSAlert(
            fisherman_id=test_fisherman.id,
            alert_type="engine_failure",
            latitude=13.0 + i,
            longitude=80.0,
            created_at=datetime.utcnow(),
        )
        db.add(sos)
    db.commit()

    dashboard = FamilySafetyPortalService.get_family_dashboard(db, test_family.id)

    assert dashboard.active_alerts == 2


def test_timeline_event_ordering(db: Session, test_family: User, test_fisherman: User):
    """Test safety timeline event ordering (newest first)."""
    access = FamilyPortalAccess(
        family_member_id=test_family.id,
        fisherman_id=test_fisherman.id,
        access_level="primary",
    )
    db.add(access)
    db.commit()

    # Create events with delays
    for i in range(3):
        FamilySafetyPortalService.create_safety_event(
            db,
            test_family.id,
            test_fisherman.id,
            "trip_started",
            f"Event {i}",
            "info",
        )

    timeline = FamilySafetyPortalService.get_safety_timeline(
        db, test_fisherman.id, test_family.id
    )

    # Should be in descending order
    for i in range(len(timeline.events) - 1):
        assert timeline.events[i].created_at >= timeline.events[i + 1].created_at


# =================================================================
# ANALYTICS ENGINE TESTS (12 tests)
# =================================================================


def test_analytics_overview(db: Session, test_fisherman: User, test_boat: Boat):
    """Test analytics overview."""
    overview = AnalyticsService.get_overview(db)

    assert overview.total_sos_alerts_today == 0
    assert overview.active_boats_now == 0
    assert overview.average_response_time_minutes >= 0


def test_analytics_overview_with_active_boats(
    db: Session, test_fisherman: User, test_boat: Boat, test_trip: Trip
):
    """Test analytics overview with active boats."""
    overview = AnalyticsService.get_overview(db)

    assert overview.active_boats_now == 1


def test_sos_trends(db: Session, test_fisherman: User):
    """Test SOS trends analytics."""
    # Create SOS alerts
    for i in range(5):
        sos = SOSAlert(
            fisherman_id=test_fisherman.id,
            alert_type="engine_failure",
            latitude=13.0,
            longitude=80.0,
            created_at=datetime.utcnow(),
            resolved_at=datetime.utcnow() + timedelta(minutes=15),
        )
        db.add(sos)
    db.commit()

    trends = AnalyticsService.get_sos_trends(db, days=7)

    assert trends.total_alerts == 5
    assert trends.resolved_alerts == 5
    assert trends.resolution_rate == 100.0


def test_response_time_metrics(db: Session, test_fisherman: User):
    """Test response time metrics."""
    # Create resolved SOS
    sos = SOSAlert(
        fisherman_id=test_fisherman.id,
        alert_type="engine_failure",
        latitude=13.0,
        longitude=80.0,
        created_at=datetime.utcnow() - timedelta(minutes=20),
        resolved_at=datetime.utcnow(),
    )
    db.add(sos)
    db.commit()

    metrics = AnalyticsService.get_response_times(db, days=1)

    assert metrics.total_resolved == 1
    assert metrics.average_response_minutes >= 19


def test_response_time_metrics_empty(db: Session):
    """Test response time metrics with no data."""
    metrics = AnalyticsService.get_response_times(db, days=1)

    assert metrics.total_resolved == 0
    assert metrics.average_response_minutes == 0


def test_active_boats_analytics(
    db: Session, test_fisherman: User, test_boat: Boat, test_trip: Trip
):
    """Test active boats analytics."""
    analytics = AnalyticsService.get_active_boats(db)

    assert analytics.boats_at_sea == 1
    assert analytics.trips_completed_today == 0


def test_risk_zones_analytics(db: Session, test_fisherman: User):
    """Test risk zone analytics."""
    zones = AnalyticsService.get_risk_zones(db, days=7)

    assert "high_risk_zones" in zones.__dict__
    assert zones.green_risk_trips >= 0
    assert zones.yellow_risk_trips >= 0
    assert zones.red_risk_trips >= 0


def test_harbor_usage_analytics(db: Session):
    """Test harbor usage analytics."""
    usage = AnalyticsService.get_harbor_usage(db, days=30)

    assert usage.total_harbor_visits >= 0


def test_boat_health_analytics(db: Session, test_boat: Boat):
    """Test boat health analytics."""
    # Update boat health
    BoatHealthService.update_health_status(db, test_boat.id, engine_hours=1000)

    analytics = AnalyticsService.get_boat_health(db)

    assert analytics.average_health_score >= 0


def test_analytics_trends_multiple_days(db: Session, test_fisherman: User):
    """Test analytics trends across multiple days."""
    # Create SOS alerts
    for i in range(3):
        sos = SOSAlert(
            fisherman_id=test_fisherman.id,
            alert_type="engine_failure",
            latitude=13.0,
            longitude=80.0,
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db.add(sos)
    db.commit()

    trends = AnalyticsService.get_sos_trends(db, days=7)

    assert trends.total_alerts == 3


def test_sos_trends_hazard_types(db: Session, test_fisherman: User):
    """Test SOS trends hazard type breakdown."""
    # Create different hazard types
    hazard_types = ["engine_failure", "collision", "weather_hit"]
    for hazard in hazard_types:
        sos = SOSAlert(
            fisherman_id=test_fisherman.id,
            alert_type=hazard,
            latitude=13.0,
            longitude=80.0,
            created_at=datetime.utcnow(),
        )
        db.add(sos)
    db.commit()

    trends = AnalyticsService.get_sos_trends(db, days=1)

    assert len(trends.top_hazard_types) == 3


def test_analytics_overview_connection_lost(
    db: Session, test_fisherman: User
):
    """Test connection lost alerts in overview."""
    from app.models.location import LocationPing

    # Create old location
    old_time = datetime.utcnow() - timedelta(minutes=45)
    location = LocationPing(
        fisherman_id=test_fisherman.id,
        latitude=13.0,
        longitude=80.0,
        accuracy_meters=10,
        timestamp=old_time,
        synced_at=old_time,
    )
    db.add(location)
    db.commit()

    overview = AnalyticsService.get_overview(db)

    assert overview.connection_lost_alerts >= 1
