"""Family Safety Portal Service Tests."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.family_link import FamilyLink
from app.models.location import LocationPing
from app.models.sos import SOSAlert, SOSStatus
from app.models.trip import Trip
from app.models.phase5 import FamilyNotification, FamilyPortalAccess
from app.services.family_portal import FamilySafetyPortalService


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

@pytest.fixture
def fisherman(db: Session) -> User:
    u = User(phone_number="+91_fp_fish", password_hash="h", full_name="FP Fisher", role="fisherman")
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture
def family(db: Session) -> User:
    u = User(phone_number="+91_fp_fam", password_hash="h", full_name="FP Family", role="family")
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture
def linked(db: Session, fisherman: User, family: User) -> FamilyPortalAccess:
    access = FamilyPortalAccess(
        family_member_id=family.id,
        fisherman_id=fisherman.id,
        access_level="view_only",
        can_view_live_location=True,
        can_view_trip_history=True,
        can_receive_alerts=True,
    )
    db.add(access); db.commit(); db.refresh(access)
    return access


# ─────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────

def test_dashboard_empty_links(db: Session, family: User):
    """Family with no links returns empty dashboard."""
    result = FamilySafetyPortalService.get_family_dashboard(db, family.id)
    assert len(result.linked_fishermen) == 0
    assert result.active_alerts == 0
    assert result.connection_lost_count == 0


def test_dashboard_with_link(db: Session, fisherman: User, family: User, linked: FamilyPortalAccess):
    """Dashboard shows one fisherman after linking."""
    result = FamilySafetyPortalService.get_family_dashboard(db, family.id)
    assert len(result.linked_fishermen) == 1
    assert result.linked_fishermen[0]["id"] == fisherman.id


def test_safety_status_safe(db: Session, fisherman: User, family: User, linked: FamilyPortalAccess):
    """Recent GPS ping returns status without error."""
    ping = LocationPing(
        user_id=fisherman.id,
        client_uuid="fp-ping-001",
        latitude=10.5,
        longitude=80.0,
        recorded_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db.add(ping); db.commit()
    status = FamilySafetyPortalService.get_fisherman_safety_status(db, fisherman.id, family.id)
    assert status.fisherman_id == fisherman.id
    assert status.active_sos is False


def test_safety_status_not_linked(db: Session, fisherman: User, family: User):
    """Unlinked fisherman raises PermissionError."""
    with pytest.raises(PermissionError):
        FamilySafetyPortalService.get_fisherman_safety_status(db, fisherman.id, family.id)


def test_timeline_empty(db: Session, fisherman: User, family: User, linked: FamilyPortalAccess):
    """Timeline with no activity returns empty events list."""
    timeline = FamilySafetyPortalService.get_safety_timeline(db, fisherman.id, family.id)
    assert timeline.fisherman_id == fisherman.id
    assert len(timeline.events) == 0


def test_notifications_empty(db: Session, family: User):
    """No notifications returns empty list."""
    notifications, total = FamilySafetyPortalService.get_family_notifications(db, family.id)
    assert total == 0
    assert notifications == []


def test_mark_notifications_read(db: Session, family: User):
    """Mark notifications as read works correctly."""
    notif = FamilyNotification(
        family_member_id=family.id,
        notification_type="push",
        message="Test notification",
        delivery_status="sent",
        created_at=datetime.utcnow(),
    )
    db.add(notif); db.commit(); db.refresh(notif)
    result = FamilySafetyPortalService.mark_notification_read(db, notif.id)
    assert result is not None
    db.refresh(notif)
    assert notif.read_at is not None
