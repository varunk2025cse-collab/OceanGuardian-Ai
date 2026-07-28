"""Incident Engine API — v2 (docs/INCIDENT_ENGINE.md)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator, get_current_user
from app.database import get_db
from app.models.phase5 import RiskIncident
from app.models.user import User
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/api/v2/incidents", tags=["incidents"])


class IncidentOut(BaseModel):
    id: int
    trip_id: int | None
    sos_alert_id: int | None
    fisherman_id: int | None
    incident_type: str | None
    severity: str | None
    status: str
    description: str | None
    resolution: str | None
    created_at: str | None
    acknowledged_at: str | None
    closed_at: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, i: RiskIncident) -> "IncidentOut":
        return cls(
            id=i.id, trip_id=i.trip_id, sos_alert_id=i.sos_alert_id, fisherman_id=i.fisherman_id,
            incident_type=i.incident_type, severity=i.severity, status=i.status,
            description=i.description, resolution=i.resolution,
            created_at=i.created_at.isoformat() if i.created_at else None,
            acknowledged_at=i.acknowledged_at.isoformat() if i.acknowledged_at else None,
            closed_at=i.closed_at.isoformat() if i.closed_at else None,
        )


class TransitionIn(BaseModel):
    status: str
    reason: str | None = None


class TimelineEventOut(BaseModel):
    timestamp: str | None
    actor_id: int | None
    previous_status: str | None
    new_status: str
    reason: str | None


@router.get("/active", response_model=list[IncidentOut])
def list_active_incidents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    return [IncidentOut.from_model(i) for i in IncidentService.get_active(db, skip=skip, limit=limit)]


def _get_incident_or_404(db: Session, incident_id: int) -> RiskIncident:
    incident = db.query(RiskIncident).filter(RiskIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incident = _get_incident_or_404(db, incident_id)
    IncidentService.authorize_view(db, incident, current_user)
    return IncidentOut.from_model(incident)


@router.get("/{incident_id}/timeline", response_model=list[TimelineEventOut])
def get_incident_timeline(incident_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incident = _get_incident_or_404(db, incident_id)
    IncidentService.authorize_view(db, incident, current_user)
    events = IncidentService.get_timeline(db, incident_id)
    return [
        TimelineEventOut(
            timestamp=e.created_at.isoformat() if e.created_at else None,
            actor_id=e.actor_id, previous_status=e.previous_status, new_status=e.new_status, reason=e.reason,
        )
        for e in events
    ]


@router.post("/{incident_id}/transition", response_model=IncidentOut)
def transition_incident(
    incident_id: int,
    payload: TransitionIn,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    incident = _get_incident_or_404(db, incident_id)
    updated = IncidentService.transition(db, incident, payload.status, current_user, payload.reason)
    return IncidentOut.from_model(updated)


@router.get("/{incident_id}/report")
def get_incident_report(incident_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incident = _get_incident_or_404(db, incident_id)
    IncidentService.authorize_view(db, incident, current_user)
    return IncidentService.generate_report(db, incident)
