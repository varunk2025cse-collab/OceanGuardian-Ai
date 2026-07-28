"""Smart Check-In System API routes — Phase 5 Week 3.

Endpoints:
  POST /api/v2/check-ins/schedule  — Create check-in schedule
  POST /api/v2/check-ins/respond   — Respond to a check-in request
  GET  /api/v2/check-ins/me        — Get my check-in status
  GET  /api/v2/check-ins/missed    — Get missed check-ins (operator)
  POST /api/v2/check-ins/escalate  — Process missed check-ins (operator)
  POST /api/v2/check-ins/process   — Process missed/overdue check-ins (bg task)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user, get_current_operator, get_current_fisherman
from app.models.user import User
from app.services.checkin import CheckInService
from app.schemas.checkin import (
    CheckInResponse,
    CheckInStatusResponse,
    MissedCheckInDetail,
    CheckInScheduleCreate,
    CheckInScheduleResponse,
    CheckInRespondRequest,
    CheckInRespondResponse,
)

router = APIRouter(prefix="/api/v2/check-ins", tags=["check-ins"])


@router.get("/me", response_model=CheckInStatusResponse)
async def get_my_checkin_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get my current check-in status."""
    if current_user.role not in ("fisherman", "operator"):
        raise HTTPException(status_code=403, detail="Only fishermen can check their status")

    status = CheckInService.get_my_checkin_status(current_user.id, db)
    if not status:
        raise HTTPException(status_code=404, detail="No active trip found")

    return status


@router.post("/respond")
async def respond_checkin(
    response: CheckInResponse,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Respond to check-in (I am safe) — legacy API."""
    if current_user.role not in ("fisherman", "operator"):
        raise HTTPException(status_code=403, detail="Only fishermen can respond to check-ins")

    try:
        result = CheckInService.respond_checkin(current_user.id, response, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/missed", response_model=List[MissedCheckInDetail])
async def get_missed_checkins(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get list of missed check-ins (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can view missed check-ins")

    missed = CheckInService.get_missed_checkins(db, limit=limit)
    return missed


@router.post("/monitor")
async def monitor_active_trips(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger monitoring of active trips (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can trigger monitoring")

    result = CheckInService.monitor_active_trips(db)
    return result


# ── Week 3 New Endpoints ──────────────────────────────────────────────────


@router.post("/schedule", response_model=CheckInScheduleResponse)
async def create_checkin_schedule(
    data: CheckInScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create check-in schedule for a trip (fisherman only)."""
    if current_user.role != "fisherman":
        raise HTTPException(status_code=403, detail="Only fishermen can create check-in schedules")

    try:
        schedule = CheckInService.create_schedule(current_user.id, data, db)
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/respond-scheduled", response_model=CheckInRespondResponse)
async def respond_scheduled_checkin(
    data: CheckInRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Respond to a scheduled check-in request (fisherman only)."""
    if current_user.role != "fisherman":
        raise HTTPException(status_code=403, detail="Only fishermen can respond to check-ins")

    try:
        result = CheckInService.respond_checkin_scheduled(current_user.id, data, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/escalate")
async def escalate_missed_checkins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger missed check-in escalation (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can trigger escalation")

    result = CheckInService.process_missed_checkins(db)
    return result


@router.post("/process")
async def process_checkins(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process missed check-ins and auto-escalate (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can process check-ins")

    result = CheckInService.process_missed_checkins(db)
    return result
