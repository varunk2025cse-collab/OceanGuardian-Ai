"""Safety State Engine API — v2 (docs/SAFETY_STATE_ENGINE.md)."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator, get_current_user
from app.database import get_db
from app.models.family_link import FamilyLink
from app.models.user import User, UserRole
from app.services.early_warning import EarlyWarning, evaluate as evaluate_early_warning
from app.services.safety_engine import SafetyEngine, SafetyEvaluation

router = APIRouter(prefix="/api/v2/safety", tags=["safety"])


class SafetyStateOut(BaseModel):
    fisherman_id: int
    safety_state: str
    safety_score: int
    communication_state: str
    freshness: str
    reasons: list[str]
    trip_status: str | None
    evaluated_at: str
    early_warning: bool
    early_warning_categories: list[str]
    # Navigation AI (docs/NAVIGATION_AI.md) — straight-line guidance to the
    # nearest known safe harbor. All null when there's no location data to
    # compute from (never a fabricated fallback).
    nearest_harbor_name: str | None = None
    nearest_harbor_km: float | None = None
    nearest_harbor_bearing: float | None = None
    nearest_harbor_direction: str | None = None
    nearest_harbor_eta_minutes: int | None = None


def _authorize(db: Session, requesting_user: User, fisherman_id: int) -> None:
    if requesting_user.role == UserRole.operator or requesting_user.id == fisherman_id:
        return
    if requesting_user.role == UserRole.family:
        linked = (
            db.query(FamilyLink)
            .filter(FamilyLink.family_user_id == requesting_user.id, FamilyLink.fisherman_id == fisherman_id)
            .first()
        )
        if linked:
            return
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized to view this fisherman's safety state")


def _to_out(ev: SafetyEvaluation, warning: EarlyWarning) -> SafetyStateOut:
    return SafetyStateOut(
        fisherman_id=ev.fisherman_id,
        safety_state=ev.safety_state,
        safety_score=ev.safety_score,
        communication_state=ev.communication_state,
        freshness=ev.freshness,
        reasons=ev.reasons,
        trip_status=ev.trip_status,
        evaluated_at=ev.evaluated_at,
        early_warning=warning.is_early_warning,
        early_warning_categories=warning.categories,
        nearest_harbor_name=ev.nearest_harbor_name,
        nearest_harbor_km=ev.nearest_harbor_km,
        nearest_harbor_bearing=ev.nearest_harbor_bearing,
        nearest_harbor_direction=ev.nearest_harbor_direction,
        nearest_harbor_eta_minutes=ev.nearest_harbor_eta_minutes,
    )


@router.get("/{fisherman_id}", response_model=SafetyStateOut)
def get_safety_state(
    fisherman_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(db, current_user, fisherman_id)
    fisherman = db.query(User).filter(User.id == fisherman_id).first()
    if not fisherman:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fisherman not found")
    ev = SafetyEngine.evaluate(db, fisherman)
    warning = evaluate_early_warning(ev)
    return _to_out(ev, warning)


@router.get("/", response_model=SafetyStateOut)
def get_my_safety_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Convenience for the mobile app: the logged-in fisherman's own state."""
    ev = SafetyEngine.evaluate(db, current_user)
    warning = evaluate_early_warning(ev)
    return _to_out(ev, warning)


@router.get("/fleet/summary", response_model=list[SafetyStateOut])
def get_fleet_safety_summary(
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Safety state for every fisherman with an in-progress trip — powers
    the rescue dashboard's high-risk vessel list."""
    from app.models.trip import Trip
    from app.services.trip_service import TripStatus

    trips = db.query(Trip).filter(Trip.status.in_(TripStatus.IN_PROGRESS)).all()
    results: list[SafetyStateOut] = []
    for trip in trips:
        fisherman = db.query(User).filter(User.id == trip.user_id).first()
        if not fisherman:
            continue
        ev = SafetyEngine.evaluate(db, fisherman)
        warning = evaluate_early_warning(ev)
        results.append(_to_out(ev, warning))
    return results
