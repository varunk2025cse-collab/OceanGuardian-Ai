"""
SOS endpoints for the fisherman mobile app.

Phase 2 security fix: PATCH /{alert_id}/status is now role-gated.
  - operator  → can set any status (acknowledged, resolved, false_alarm)
  - fisherman → can ONLY set their OWN alert to false_alarm
  - family    → blocked entirely
This closes the Phase 1 bug where any user could resolve anyone's alert.

Phase 2 additions:
  - trigger accepts priority field (default: high for all SOS triggers)
  - priority and rescue_notes on status update
  - pagination on /active and /me/history
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.sos import SOSAlert, SOSStatus
from app.schemas.sos import SOSAlertIn, SOSAlertOut, SOSStatusUpdate
from app.services.sos_service import notify_emergency_contacts
from app.services.incident_service import IncidentService
from app.services.notification_service import NotificationEngine, NotificationPriority

logger = logging.getLogger("oceanguardian.sos")

router = APIRouter(prefix="/api/v1/sos", tags=["sos"])


@router.post("/trigger", response_model=SOSAlertOut, status_code=status.HTTP_201_CREATED)
def trigger_sos(
    payload: SOSAlertIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Idempotent on client_uuid. Any authenticated user can trigger SOS
    (fisherman in an emergency, or a family member triggering on behalf of
    someone in distress). Default priority = high unless specified.
    """
    existing = db.query(SOSAlert).filter(SOSAlert.client_uuid == payload.client_uuid).first()
    if existing:
        return existing

    alert = SOSAlert(
        user_id=current_user.id,
        priority="high",          # sensible default; operators can escalate to critical
        **payload.model_dump()
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    notify_emergency_contacts(current_user, alert)

    # The alert itself is already committed above — everything from here
    # down is auxiliary (incident bookkeeping, family notification). A
    # failure in either must never turn into a failed SOS request: per the
    # governing safety principle, SOS must work even when other subsystems
    # (notification provider, etc.) are down. Each is isolated so one
    # failing doesn't take out the other, and both are logged loudly for
    # operator/ops visibility rather than silently swallowed.
    try:
        IncidentService.create_from_sos(db, alert)
    except Exception:
        logger.exception("Failed to auto-create incident for SOS alert %s — alert itself is safe.", alert.id)

    try:
        NotificationEngine.notify_family_of_event(
            db,
            fisherman_id=current_user.id,
            message=f"{current_user.full_name} triggered an SOS alert ({alert.alert_type or 'MANUAL_SOS'}).",
            related_event_id=alert.id,
            priority=NotificationPriority.critical,
        )
    except Exception:
        logger.exception("Failed to dispatch family notification for SOS alert %s — alert itself is safe.", alert.id)

    return alert


@router.get("/active", response_model=list[SOSAlertOut])
def list_active_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Active + acknowledged alerts. Accessible by all roles:
    - Fisherman: sees all active alerts (e.g. to know if nearby boats are in trouble)
    - Operator: consumed by the Rescue Dashboard (full view with pagination)
    - Family: used to check if their fisherman has an active alert
    For the richer operator view (with fisherman details), use GET /admin/sos.
    """
    return (
        db.query(SOSAlert)
        .filter(SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged]))
        .order_by(SOSAlert.received_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.patch("/{alert_id}/status", response_model=SOSAlertOut)
def update_sos_status(
    alert_id: int,
    payload: SOSStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SECURITY-FIXED from MVP:
      operator  → any status transition on any alert
      fisherman → false_alarm only, and only on their own alert
      family    → blocked
    """
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS alert not found")

    new_status = SOSStatus(payload.status)

    if current_user.role == UserRole.operator:
        # Operators can do anything
        pass
    elif current_user.role == UserRole.fisherman:
        # Fishermen may only mark their OWN alert as false_alarm
        if alert.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only update your own SOS alerts")
        if new_status != SOSStatus.false_alarm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Fishermen may only mark their own alert as false_alarm")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only operators or the triggering fisherman can update SOS status")

    alert.status = new_status
    if payload.rescue_notes is not None:
        alert.rescue_notes = payload.rescue_notes
    if payload.priority is not None:
        alert.priority = payload.priority
    if payload.resolved_note is not None:
        alert.resolved_note = payload.resolved_note

    if new_status == SOSStatus.acknowledged:
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.now(timezone.utc)
    elif new_status in (SOSStatus.resolved, SOSStatus.false_alarm):
        alert.resolved_by = current_user.id
        alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


@router.get("/me/history", response_model=list[SOSAlertOut])
def my_sos_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SOSAlert)
        .filter(SOSAlert.user_id == current_user.id)
        .order_by(SOSAlert.received_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
