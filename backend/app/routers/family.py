"""
Family Tracking Dashboard API.

A family account links itself to a fisherman by phone number (the fisherman
shares their registered number once, e.g. when signing up together at a
harbor kiosk). After that, GET /status returns each linked fisherman's last
known position, last-seen time, and whether they currently have an active
SOS -- the three things a waiting family member actually needs.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.family_link import FamilyLink
from app.models.location import LocationPing
from app.models.sos import SOSAlert, SOSStatus
from app.schemas.family import FamilyLinkCreate, FishermanStatusOut
from app.services.incident_service import IncidentStatus
from app.models.phase5 import RiskIncident
from app.services.safety_engine import SafetyEngine
from app.services.tracking_service import compute_freshness

router = APIRouter(prefix="/api/v1/family", tags=["family"])


def _require_family_role(user: User):
    if user.role != UserRole.family:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only family accounts can use this endpoint",
        )


@router.post("/link", status_code=status.HTTP_201_CREATED)
def link_fisherman(
    payload: FamilyLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_family_role(current_user)

    fisherman = (
        db.query(User)
        .filter(User.phone_number == payload.fisherman_phone_number, User.role == UserRole.fisherman)
        .first()
    )
    if not fisherman:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No fisherman with that phone number")

    existing = (
        db.query(FamilyLink)
        .filter(FamilyLink.fisherman_id == fisherman.id, FamilyLink.family_user_id == current_user.id)
        .first()
    )
    if existing:
        return {"detail": "Already linked", "fisherman_id": fisherman.id}

    link = FamilyLink(fisherman_id=fisherman.id, family_user_id=current_user.id, relation=payload.relation)
    db.add(link)
    db.commit()
    return {"detail": "Linked", "fisherman_id": fisherman.id}


@router.delete("/unlink/{fisherman_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_fisherman(
    fisherman_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a fisherman link from the family account."""
    _require_family_role(current_user)

    link = (
        db.query(FamilyLink)
        .filter(FamilyLink.fisherman_id == fisherman_id, FamilyLink.family_user_id == current_user.id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()
    return None


@router.get("/status", response_model=list[FishermanStatusOut])
def linked_fishermen_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_family_role(current_user)

    links = db.query(FamilyLink).filter(FamilyLink.family_user_id == current_user.id).all()

    results: list[FishermanStatusOut] = []
    for link in links:
        fisherman = link.fisherman
        last_ping = (
            db.query(LocationPing)
            .filter(LocationPing.user_id == fisherman.id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )
        has_active_sos = (
            db.query(SOSAlert)
            .filter(
                SOSAlert.user_id == fisherman.id,
                SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged]),
            )
            .first()
            is not None
        )
        safety = SafetyEngine.evaluate(db, fisherman)
        open_incident = (
            db.query(RiskIncident)
            .filter(RiskIncident.fisherman_id == fisherman.id, RiskIncident.status.in_(IncidentStatus.OPEN))
            .order_by(RiskIncident.created_at.desc())
            .first()
        )
        results.append(
            FishermanStatusOut(
                fisherman_id=fisherman.id,
                full_name=fisherman.full_name,
                boat_name=fisherman.boat_name,
                last_latitude=last_ping.latitude if last_ping else None,
                last_longitude=last_ping.longitude if last_ping else None,
                last_seen_at=last_ping.recorded_at if last_ping else None,
                active_sos=has_active_sos,
                freshness=compute_freshness(last_ping.recorded_at if last_ping else None).value,
                safety_state=safety.safety_state,
                incident_status=open_incident.status if open_incident else None,
            )
        )
    return results
