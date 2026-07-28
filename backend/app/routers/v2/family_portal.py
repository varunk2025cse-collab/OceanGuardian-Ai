"""Family Safety Portal API routes — v2 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.family_portal import (
    FamilySafetyPortalService,
    SafetyStatusResponse,
    FamilySafetyTimelineResponse,
    FamilyDashboardResponse,
    FamilyNotificationResponse,
)

router = APIRouter(prefix="/api/v2/family", tags=["family-safety"])


@router.get("/dashboard", response_model=FamilyDashboardResponse)
async def get_family_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get family safety dashboard (family member only)."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can access dashboard")

    dashboard = FamilySafetyPortalService.get_family_dashboard(db, current_user.id)
    return dashboard


@router.get("/fisherman/{fisherman_id}/safety-status", response_model=SafetyStatusResponse)
async def get_fisherman_safety_status(
    fisherman_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get fisherman safety status for family member."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can access this")

    try:
        status = FamilySafetyPortalService.get_fisherman_safety_status(db, fisherman_id, current_user.id)
        return status
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/fisherman/{fisherman_id}/timeline", response_model=FamilySafetyTimelineResponse)
async def get_fisherman_timeline(
    fisherman_id: int,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get fisherman safety timeline for family member."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can access this")

    try:
        timeline = FamilySafetyPortalService.get_safety_timeline(db, fisherman_id, current_user.id, limit=limit)
        return timeline
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/notifications/{notification_id}/mark-read", response_model=dict)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark family notification as read."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can mark notifications")

    notification = FamilySafetyPortalService.mark_notification_read(db, notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.family_member_id != current_user.id:
        raise HTTPException(status_code=403, detail="This notification is not for you")

    return {
        "id": notification.id,
        "read_at": notification.read_at,
    }


@router.get("/notifications", response_model=dict)
async def get_family_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get family notifications."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can access notifications")

    notifications, total = FamilySafetyPortalService.get_family_notifications(
        db, current_user.id, skip=skip, limit=limit
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "notifications": [
            {
                "id": n.id,
                "notification_type": n.notification_type,
                "message": n.message,
                "sent_at": n.sent_at,
                "read_at": n.read_at,
                "delivery_status": n.delivery_status,
            }
            for n in notifications
        ],
    }


@router.get("/alerts", response_model=dict)
async def get_family_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active alerts for family."""
    if current_user.role != "family":
        raise HTTPException(status_code=403, detail="Only family members can access alerts")

    dashboard = FamilySafetyPortalService.get_family_dashboard(db, current_user.id)

    return {
        "active_alerts": dashboard.active_alerts,
        "connection_lost_count": dashboard.connection_lost_count,
        "linked_fishermen": dashboard.linked_fishermen,
    }
