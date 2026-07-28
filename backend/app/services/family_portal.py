"""Family Safety Portal Service — family dashboard, safety status, and notifications."""
import json
from datetime import datetime, timedelta, date
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.phase5 import (
    FamilyPortalAccess,
    FamilySafetyEvent,
    FamilyNotification,
)
from app.models.trip import Trip
from app.models.location import LocationPing
from app.models.sos import SOSAlert


# =================================================================
# SCHEMAS
# =================================================================


class SafetyStatusResponse(BaseModel):
    """Family member view of fisherman safety status."""
    fisherman_id: int
    fisherman_phone: str
    current_status: str  # "at_sea", "at_harbor", "at_home", "unknown"
    last_known_location: Optional[dict]  # {lat, lng, accuracy}
    last_update_minutes_ago: int
    trip_status: Optional[str]  # "active", "completed", "cancelled"
    trip_start_time: Optional[datetime]
    active_sos: bool
    sos_details: Optional[dict]
    connection_lost_warning: bool  # GPS no update for > 30 min
    last_check_in_time: Optional[datetime]


class FamilySafetyEventResponse(BaseModel):
    """Safety event notification."""
    id: int
    event_type: str  # "trip_started", "sos_alert", "trip_completed", "location_update"
    event_description: str
    severity: str  # "info", "warning", "critical"
    location: Optional[dict]
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


class FamilySafetyTimelineResponse(BaseModel):
    """Safety timeline for fisherman."""
    fisherman_id: int
    trip_id: Optional[int]
    events: List[FamilySafetyEventResponse]
    total_events: int


class FamilyDashboardResponse(BaseModel):
    """Family dashboard overview."""
    linked_fishermen: List[dict]  # [{"id", "name", "phone", "status", "risk_badge"}]
    active_alerts: int
    total_events_today: int
    connection_lost_count: int
    last_update_time: datetime


class FamilyNotificationResponse(BaseModel):
    """Family notification."""
    id: int
    notification_type: str  # "push", "sms", "email"
    message: str
    severity: str
    sent_at: datetime
    read_at: Optional[datetime]
    delivery_status: str  # "pending", "sent", "failed"

    class Config:
        from_attributes = True


# =================================================================
# FAMILY SAFETY PORTAL SERVICE
# =================================================================


class FamilySafetyPortalService:
    """Family Safety Portal Service."""

    @staticmethod
    def get_fisherman_safety_status(
        db: Session, fisherman_id: int, family_member_id: int
    ) -> SafetyStatusResponse:
        """Get fisherman safety status for family member."""
        # Verify access
        access = (
            db.query(FamilyPortalAccess)
            .filter(
                FamilyPortalAccess.fisherman_id == fisherman_id,
                FamilyPortalAccess.family_member_id == family_member_id,
            )
            .first()
        )
        if not access or not access.can_view_live_location:
            raise PermissionError("No access to this fisherman's data")

        # Get latest location — user_id is the correct column on LocationPing
        latest_location = (
            db.query(LocationPing)
            .filter(LocationPing.user_id == fisherman_id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )

        # Get active trip — user_id is the correct column on Trip
        active_trip = (
            db.query(Trip)
            .filter(Trip.user_id == fisherman_id, Trip.end_time.is_(None))
            .first()
        )

        # Get active SOS — user_id is the correct column on SOSAlert
        active_sos = (
            db.query(SOSAlert)
            .filter(
                SOSAlert.user_id == fisherman_id,
                SOSAlert.resolved_at.is_(None),
            )
            .order_by(SOSAlert.triggered_at.desc())
            .first()
        )

        # Determine status
        last_update = None
        last_update_minutes = 9999
        last_known_location = None

        if latest_location:
            last_update = latest_location.recorded_at
            last_update_minutes = int((datetime.utcnow() - last_update).total_seconds() / 60)
            last_known_location = {
                "lat": latest_location.latitude,
                "lng": latest_location.longitude,
                "accuracy": latest_location.accuracy_meters,
            }

        # Determine current status
        current_status = "unknown"
        if active_trip:
            current_status = "at_sea"
        elif last_update_minutes < 60:
            current_status = "at_home"

        # Connection lost warning (no GPS for > 30 min)
        connection_lost = last_update_minutes > 30

        sos_details = None
        if active_sos:
            sos_details = {
                "id": active_sos.id,
                "alert_type": active_sos.alert_type,
                "latitude": active_sos.latitude,
                "longitude": active_sos.longitude,
                "created_at": active_sos.triggered_at,
            }

        return SafetyStatusResponse(
            fisherman_id=fisherman_id,
            fisherman_phone=access.fisherman.phone_number if access.fisherman else "N/A",
            current_status=current_status,
            last_known_location=last_known_location,
            last_update_minutes_ago=min(last_update_minutes, 9999),
            trip_status="active" if active_trip else None,
            trip_start_time=active_trip.start_time if active_trip else None,
            active_sos=active_sos is not None,
            sos_details=sos_details,
            connection_lost_warning=connection_lost,
            last_check_in_time=last_update,
        )

    @staticmethod
    def get_safety_timeline(
        db: Session, fisherman_id: int, family_member_id: int, limit: int = 50
    ) -> FamilySafetyTimelineResponse:
        """Get safety timeline for fisherman."""
        # Verify access
        access = (
            db.query(FamilyPortalAccess)
            .filter(
                FamilyPortalAccess.fisherman_id == fisherman_id,
                FamilyPortalAccess.family_member_id == family_member_id,
            )
            .first()
        )
        if not access:
            raise PermissionError("No access to this fisherman's data")

        # Get all safety events
        events = (
            db.query(FamilySafetyEvent)
            .filter(FamilySafetyEvent.fisherman_id == fisherman_id)
            .order_by(FamilySafetyEvent.created_at.desc())
            .limit(limit)
            .all()
        )

        event_responses = [
            FamilySafetyEventResponse(
                id=e.id,
                event_type=e.event_type,
                event_description=e.event_description,
                severity=e.severity,
                location=json.loads(e.location_json) if e.location_json else None,
                created_at=e.created_at,
                read_at=e.read_at,
            )
            for e in events
        ]

        trip_id = None
        active_trip = (
            db.query(Trip)
            .filter(Trip.user_id == fisherman_id, Trip.end_time.is_(None))
            .first()
        )
        if active_trip:
            trip_id = active_trip.id

        return FamilySafetyTimelineResponse(
            fisherman_id=fisherman_id,
            trip_id=trip_id,
            events=event_responses,
            total_events=len(events),
        )

    @staticmethod
    def get_family_dashboard(
        db: Session, family_member_id: int
    ) -> FamilyDashboardResponse:
        """Get family dashboard."""
        # Get all linked fishermen
        links = (
            db.query(FamilyPortalAccess)
            .filter(FamilyPortalAccess.family_member_id == family_member_id)
            .all()
        )

        linked_fishermen = []
        for link in links:
            fisherman = link.fisherman
            if not fisherman:
                continue

            # Get latest location
            latest_location = (
                db.query(LocationPing)
                .filter(LocationPing.user_id == fisherman.id)
                .order_by(LocationPing.recorded_at.desc())
                .first()
            )

            # Get active trip
            active_trip = (
                db.query(Trip)
                .filter(Trip.user_id == fisherman.id, Trip.end_time.is_(None))
                .first()
            )

            # Get active SOS
            active_sos = (
                db.query(SOSAlert)
                .filter(
                    SOSAlert.user_id == fisherman.id,
                    SOSAlert.resolved_at.is_(None),
                )
                .first()
            )

            status = "at_sea" if active_trip else "at_home"
            risk_badge = "🔴 ALERT" if active_sos else "🟢 OK" if latest_location else "⚪ UNKNOWN"

            linked_fishermen.append({
                "id": fisherman.id,
                "name": fisherman.full_name,
                "phone": fisherman.phone_number,
                "status": status,
                "risk_badge": risk_badge,
                "last_update": latest_location.recorded_at if latest_location else None,
            })

        # Count active alerts
        active_alerts = (
            db.query(SOSAlert)
            .join(FamilyPortalAccess, SOSAlert.user_id == FamilyPortalAccess.fisherman_id)
            .filter(
                FamilyPortalAccess.family_member_id == family_member_id,
                SOSAlert.resolved_at.is_(None),
            )
            .count()
        )

        # Count events today
        today_date = datetime.utcnow().date()
        today_start = datetime.combine(today_date, datetime.min.time())
        events_today = (
            db.query(FamilySafetyEvent)
            .join(FamilyPortalAccess, FamilySafetyEvent.fisherman_id == FamilyPortalAccess.fisherman_id)
            .filter(
                FamilyPortalAccess.family_member_id == family_member_id,
                FamilySafetyEvent.created_at >= today_start,
            )
            .count()
        )

        # Count connection lost
        connection_lost = 0
        for link in links:
            latest_location = (
                db.query(LocationPing)
                .filter(LocationPing.user_id == link.fisherman_id)
                .order_by(LocationPing.recorded_at.desc())
                .first()
            )
            if latest_location:
                minutes_ago = int((datetime.utcnow() - latest_location.recorded_at).total_seconds() / 60)
                if minutes_ago > 30:
                    connection_lost += 1

        return FamilyDashboardResponse(
            linked_fishermen=linked_fishermen,
            active_alerts=active_alerts,
            total_events_today=events_today,
            connection_lost_count=connection_lost,
            last_update_time=datetime.utcnow(),
        )

    @staticmethod
    def create_safety_event(
        db: Session,
        family_member_id: int,
        fisherman_id: int,
        event_type: str,
        description: str,
        severity: str,
        location_json: Optional[str] = None,
        trip_id: Optional[int] = None,
        sos_alert_id: Optional[int] = None,
    ) -> FamilySafetyEvent:
        """Create safety event for family."""
        event = FamilySafetyEvent(
            family_member_id=family_member_id,
            fisherman_id=fisherman_id,
            event_type=event_type,
            event_description=description,
            severity=severity,
            location_json=location_json,
            trip_id=trip_id,
            sos_alert_id=sos_alert_id,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def mark_notification_read(db: Session, notification_id: int) -> FamilyNotification:
        """Mark family notification as read."""
        notification = (
            db.query(FamilyNotification)
            .filter(FamilyNotification.id == notification_id)
            .first()
        )
        if notification:
            notification.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def get_family_notifications(
        db: Session, family_member_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[List[FamilyNotification], int]:
        """Get family notifications."""
        total = (
            db.query(FamilyNotification)
            .filter(FamilyNotification.family_member_id == family_member_id)
            .count()
        )

        notifications = (
            db.query(FamilyNotification)
            .filter(FamilyNotification.family_member_id == family_member_id)
            .order_by(FamilyNotification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return notifications, total
