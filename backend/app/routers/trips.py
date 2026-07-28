"""
Trip management — start/end/transition fishing trips.

A fisherman can only have ONE in-progress trip at a time (active, returning,
or emergency — see app.services.trip_service.TripStatus.IN_PROGRESS). The
phone enforces this in the UI, the API enforces it server-side. Starting a
second trip while one is in progress raises a 409 — the fisherman must end
the current trip first.

State machine and transition rules live in app.services.trip_service; this
router stays thin.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_fisherman, get_current_user
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip import TripStart, TripEnd, TripTransition, TripOut
from app.services.trip_service import TripService

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])


@router.post("/start", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def start_trip(
    payload: TripStart,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    return TripService.start_trip(
        db,
        user_id=current_user.id,
        boat_id=payload.boat_id,
        start_latitude=payload.start_latitude,
        start_longitude=payload.start_longitude,
        destination=payload.destination,
        estimated_return_at=payload.estimated_return_at,
        notes=payload.notes,
    )


@router.post("/end", response_model=TripOut)
def end_trip(
    payload: TripEnd,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    return TripService.end_trip(db, current_user.id, payload.notes)


@router.patch("/{trip_id}/status", response_model=TripOut)
def transition_trip(
    trip_id: int,
    payload: TripTransition,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    """Fisherman-initiated transitions — e.g. marking a trip RETURNING once
    heading back to harbor, or CANCELLED before departure. EMERGENCY is a
    legal target here too (manual "I need help" without a full SOS), but
    the SOS flow will be the primary path once it's wired in a later pass.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return TripService.transition(db, trip, payload.status, payload.notes)


@router.get("/active", response_model=TripOut | None)
def get_active_trip(
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    return TripService.get_active_trip(db, current_user.id)


@router.get("/history", response_model=list[TripOut])
def trip_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Trip)
        .filter(Trip.user_id == current_user.id)
        .order_by(Trip.start_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
