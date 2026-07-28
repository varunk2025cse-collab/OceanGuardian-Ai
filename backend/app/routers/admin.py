"""
Admin/operator endpoints — React Rescue Dashboard only.

All endpoints require the `operator` role (enforced by get_current_operator).
Returns richer joined data than the fisherman-facing equivalents:
  - SOS alerts include full fisherman profile
  - Fishermen list includes last location, active trip, and risk score

Prefix: /api/v1/admin
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_operator
from app.models.boat import Boat
from app.models.location import LocationPing
from app.models.sos import SOSAlert, SOSStatus
from app.models.trip import Trip
from app.models.weather_alert import WeatherAlert
from app.models.user import User, UserRole
from app.schemas.admin import (
    DashboardStats, FishermanAdminOut, SOSAlertAdminOut,
    PaginatedSOS, PaginatedFishermen, ActiveTripSummary,
)
from app.schemas.location import LocationOut
from app.schemas.user import UserOut
from app.routers.risk import compute_risk
from app.services.safety_engine import SafetyEngine
from app.services.trip_service import TripStatus

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_sos_admin_out(alert: SOSAlert, db: Session) -> SOSAlertAdminOut:
    fisherman = db.query(User).filter(User.id == alert.user_id).first()
    ack_user = db.query(User).filter(User.id == alert.acknowledged_by).first() if alert.acknowledged_by else None
    res_user = db.query(User).filter(User.id == alert.resolved_by).first() if alert.resolved_by else None
    return SOSAlertAdminOut(
        id=alert.id, client_uuid=alert.client_uuid,
        status=alert.status, priority=alert.priority,
        rescue_notes=alert.rescue_notes,
        triggered_at=alert.triggered_at, received_at=alert.received_at,
        resolved_at=alert.resolved_at, resolved_note=alert.resolved_note,
        latitude=alert.latitude, longitude=alert.longitude,
        accuracy_meters=alert.accuracy_meters,
        battery_level_percent=alert.battery_level_percent,
        message=alert.message,
        fisherman=UserOut.model_validate(fisherman),
        acknowledged_by_user=UserOut.model_validate(ack_user) if ack_user else None,
        resolved_by_user=UserOut.model_validate(res_user) if res_user else None,
    )


# ── Dashboard overview ────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    return DashboardStats(
        active_sos_count=db.query(SOSAlert).filter(
            SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged])).count(),
        active_trips_count=db.query(Trip).filter(Trip.status.in_(TripStatus.IN_PROGRESS)).count(),
        fishermen_count=db.query(User).filter(
            User.role == UserRole.fisherman, User.is_active.is_(True)).count(),
        critical_weather_count=db.query(WeatherAlert).filter(
            WeatherAlert.valid_from <= now,
            WeatherAlert.valid_until >= now,
            WeatherAlert.severity == "danger",
        ).count(),
    )


# ── SOS management ────────────────────────────────────────────────────────────

@router.get("/sos", response_model=PaginatedSOS)
def list_all_sos(
    sos_status: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    query = db.query(SOSAlert)
    if sos_status:
        query = query.filter(SOSAlert.status == sos_status)
    total = query.count()
    alerts = query.order_by(SOSAlert.received_at.desc()).offset(skip).limit(limit).all()
    return PaginatedSOS(
        items=[_build_sos_admin_out(a, db) for a in alerts],
        total=total, skip=skip, limit=limit,
    )


@router.get("/sos/{alert_id}", response_model=SOSAlertAdminOut)
def get_sos_detail(
    alert_id: int,
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS alert not found")
    return _build_sos_admin_out(alert, db)


@router.patch("/sos/{alert_id}/status", response_model=SOSAlertAdminOut)
def admin_update_sos_status(
    alert_id: int,
    payload: dict,
    current_op: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Operator-only: full authority over any status transition."""
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS alert not found")

    new_status_str = payload.get("status")
    if new_status_str:
        from app.models.sos import SOSStatus as SS
        alert.status = SS(new_status_str)
        if alert.status == SS.acknowledged:
            alert.acknowledged_by = current_op.id
        elif alert.status in (SS.resolved, SS.false_alarm):
            alert.resolved_by = current_op.id
            alert.resolved_at = datetime.now(timezone.utc)

    if "rescue_notes" in payload:
        alert.rescue_notes = payload["rescue_notes"]
    if "priority" in payload:
        alert.priority = payload["priority"]
    if "resolved_note" in payload:
        alert.resolved_note = payload["resolved_note"]

    db.commit()
    db.refresh(alert)
    return _build_sos_admin_out(alert, db)


# ── Fishermen overview ────────────────────────────────────────────────────────

@router.get("/fishermen", response_model=PaginatedFishermen)
def list_fishermen(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    total = db.query(User).filter(User.role == UserRole.fisherman, User.is_active.is_(True)).count()
    fishermen = (
        db.query(User)
        .filter(User.role == UserRole.fisherman, User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .offset(skip).limit(limit).all()
    )
    items = []
    for f in fishermen:
        last_ping = (
            db.query(LocationPing)
            .filter(LocationPing.user_id == f.id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )
        active_trip = db.query(Trip).filter(Trip.user_id == f.id, Trip.status.in_(TripStatus.IN_PROGRESS)).first()
        has_sos = db.query(SOSAlert).filter(
            SOSAlert.user_id == f.id,
            SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged]),
        ).first() is not None

        # Safety semantics audit finding (Final Release Engineering Phase G):
        # this previously defaulted a fisherman with NO location data to
        # {"score": 0, "label": "safe", "color": "green"} — presenting an
        # absence of data as an affirmative safety claim, exactly the
        # anti-pattern the governing brief prohibits. A fisherman with no
        # location on record is UNKNOWN, not safe.
        risk = (
            compute_risk(last_ping.latitude, last_ping.longitude, db)
            if last_ping else {"score": -1, "label": "unknown", "color": "gray"}
        )
        safety_state = SafetyEngine.evaluate(db, f).safety_state

        active_trip_summary = None
        if active_trip:
            boat = db.query(Boat).filter(Boat.id == active_trip.boat_id).first() if active_trip.boat_id else None
            active_trip_summary = ActiveTripSummary(
                id=active_trip.id, status=active_trip.status,
                start_time=active_trip.start_time,
                estimated_return_at=active_trip.estimated_return_at,
                destination=active_trip.destination,
                boat_name=boat.name if boat else None,
            )

        items.append(FishermanAdminOut(
            id=f.id, full_name=f.full_name, phone_number=f.phone_number,
            boat_name=f.boat_name, boat_registration_number=f.boat_registration_number,
            home_harbor=f.home_harbor,
            emergency_contact_name=f.emergency_contact_name,
            emergency_contact_phone=f.emergency_contact_phone,
            preferred_language=f.preferred_language,
            last_location=LocationOut.model_validate(last_ping) if last_ping else None,
            active_trip=active_trip_summary,
            active_sos=has_sos,
            risk_score=risk["score"],
            risk_label=risk["label"],
            safety_state=safety_state,
        ))
    return PaginatedFishermen(items=items, total=total, skip=skip, limit=limit)


@router.get("/fishermen/{fisherman_id}/locations", response_model=list[LocationOut])
def fisherman_locations(
    fisherman_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """GPS trail for a specific fisherman, used by the Rescue Dashboard map."""
    return (
        db.query(LocationPing)
        .filter(LocationPing.user_id == fisherman_id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(limit)
        .all()
    )
