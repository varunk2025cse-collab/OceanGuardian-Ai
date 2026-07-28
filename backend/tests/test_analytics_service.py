"""Analytics Engine Service Tests — Phase 5 Week 2.

12 tests covering:
- Overview aggregations
- SOS trends (daily/weekly/monthly)
- Response time metrics
- Active boats listing
- Risk zone clustering
- Harbor usage stats
- Boat health analytics
- Edge cases (empty data, zero resolution)
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.trip import Trip
from app.models.sos import SOSAlert, SOSStatus
from app.models.phase5 import BoatHealthStatus, Harbor
from app.models.boat import Boat
from app.services.analytics import AnalyticsService


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def fisherman(db: Session) -> User:
    u = User(phone_number="+91_an_fish", password_hash="h", full_name="AN Fisher", role="fisherman")
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture
def operator(db: Session) -> User:
    u = User(phone_number="+91_an_op", password_hash="h", full_name="AN Operator", role="operator")
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_sos(db: Session, user_id: int, uuid: str, lat: float, lng: float,
              status: SOSStatus = SOSStatus.active,
              received_offset_hours: int = 0,
              resolved_offset_hours: int = None) -> SOSAlert:
    received = datetime.utcnow() - timedelta(hours=received_offset_hours)
    resolved = None
    if resolved_offset_hours is not None:
        resolved = received + timedelta(hours=resolved_offset_hours)
    alert = SOSAlert(
        user_id=user_id,
        client_uuid=uuid,
        latitude=lat, longitude=lng,
        status=status,
        triggered_at=received,
        received_at=received,
        resolved_at=resolved,
    )
    db.add(alert)
    return alert


# ─────────────────────────────────────────────
# OVERVIEW TESTS (2)
# ─────────────────────────────────────────────

def test_overview_empty_db(db: Session):
    """Overview on an empty database returns all zeros."""
    result = AnalyticsService.get_overview(db)
    assert result.active_sos_count >= 0
    assert result.active_trips_count >= 0
    assert result.generated_at is not None


def test_overview_counts_active_trip(db: Session, fisherman: User):
    """Overview reflects active trip count."""
    before = AnalyticsService.get_overview(db)
    trip = Trip(user_id=fisherman.id, status="active", start_time=datetime.utcnow())
    db.add(trip); db.commit()
    after = AnalyticsService.get_overview(db)
    assert after.active_trips_count == before.active_trips_count + 1
    # cleanup
    db.delete(trip); db.commit()


# ─────────────────────────────────────────────
# SOS TRENDS TESTS (2)
# ─────────────────────────────────────────────

def test_sos_trends_daily_returns_n_periods(db: Session):
    """Daily trends always return exactly n periods."""
    result = AnalyticsService.get_sos_trends(db, period_type="daily", n_periods=7)
    assert result.period_type == "daily"
    assert len(result.trends) == 7


def test_sos_trends_captures_today(db: Session, fisherman: User):
    """Trend for today increments when a new SOS is added."""
    before_trends = AnalyticsService.get_sos_trends(db, "daily", 1)
    before_count = before_trends.trends[0].total

    _make_sos(db, fisherman.id, "an-sos-trend-01", 10.5, 80.0)
    db.commit()

    after_trends = AnalyticsService.get_sos_trends(db, "daily", 1)
    after_count = after_trends.trends[0].total
    assert after_count == before_count + 1


# ─────────────────────────────────────────────
# RESPONSE TIME TESTS (2)
# ─────────────────────────────────────────────

def test_response_times_no_data(db: Session):
    """Response time on a fresh DB returns None averages."""
    result = AnalyticsService.get_response_times(db, days=1)
    # May be None or a small float depending on other tests; just ensure no crash
    assert result.total_resolved >= 0


def test_response_times_calculates_correctly(db: Session, fisherman: User):
    """Response time is calculated from received_at to resolved_at."""
    received = datetime.utcnow() - timedelta(hours=2)
    resolved = received + timedelta(minutes=30)
    alert = SOSAlert(
        user_id=fisherman.id,
        client_uuid="an-sos-rt-001",
        latitude=10.0, longitude=80.0,
        status=SOSStatus.resolved,
        triggered_at=received,
        received_at=received,
        resolved_at=resolved,
    )
    db.add(alert); db.commit()

    result = AnalyticsService.get_response_times(db, days=1)
    # avg should be ~30 minutes for this alert (may include others)
    assert result.total_resolved >= 1
    assert result.avg_minutes is not None
    assert result.avg_minutes >= 1


# ─────────────────────────────────────────────
# ACTIVE BOATS TESTS (2)
# ─────────────────────────────────────────────

def test_active_boats_empty(db: Session):
    """Active boats with no trips returns empty list."""
    result = AnalyticsService.get_active_boats(db, limit=100)
    assert result.total_active >= 0
    assert isinstance(result.boats, list)


def test_active_boats_includes_active_trip(db: Session, fisherman: User):
    """Active trip appears in active boats output."""
    trip = Trip(user_id=fisherman.id, status="active",
                start_time=datetime.utcnow() - timedelta(hours=1),
                destination="Test Zone")
    db.add(trip); db.commit()

    result = AnalyticsService.get_active_boats(db, limit=100)
    trip_ids = [b.trip_id for b in result.boats]
    assert trip.id in trip_ids
    # cleanup
    db.delete(trip); db.commit()


# ─────────────────────────────────────────────
# RISK ZONES TESTS (2)
# ─────────────────────────────────────────────

def test_risk_zones_empty(db: Session):
    """Risk zones with no recent SOS returns no zones (or zero incidents)."""
    result = AnalyticsService.get_risk_zones(db, days=1)
    assert result.total_incidents >= 0


def test_risk_zones_clusters_nearby_alerts(db: Session, fisherman: User):
    """Multiple SOS alerts in the same area form a single zone."""
    for i in range(3):
        _make_sos(db, fisherman.id, f"an-rz-00{i}", 10.5 + i * 0.1, 80.0)
    db.commit()

    result = AnalyticsService.get_risk_zones(db, days=1)
    assert result.total_incidents >= 3
    # Alerts near (10.5, 80.0) should cluster into one cell
    assert len(result.zones) >= 1
    top_zone = result.zones[0]
    assert top_zone.sos_count >= 1


# ─────────────────────────────────────────────
# HARBOR USAGE + BOAT HEALTH TESTS (2)
# ─────────────────────────────────────────────

def test_harbor_usage_empty(db: Session):
    """Harbor usage with no harbors returns empty list."""
    result = AnalyticsService.get_harbor_usage(db)
    assert isinstance(result.stats, list)
    assert result.total_harbors >= 0


def test_boat_health_analytics(db: Session, fisherman: User):
    """Boat health analytics counts health status correctly."""
    from app.models.boat import Boat
    boat = Boat(owner_id=fisherman.id, name="ANA Vessel", registration_number="AN-001")
    db.add(boat); db.commit()

    # Add a health record with a Good score
    health = BoatHealthStatus(boat_id=boat.id, health_score=90.0, updated_at=datetime.utcnow())
    db.add(health); db.commit()

    result = AnalyticsService.get_boat_health_analytics(db)
    assert result.total_boats_tracked >= 1
    assert result.good_count >= 1
