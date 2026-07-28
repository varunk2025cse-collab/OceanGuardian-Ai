"""
Incident engine (docs/INCIDENT_ENGINE.md) — the 8-state lifecycle a real
emergency goes through from the moment it's received to closure, with a
full, immutable audit trail (IncidentEvent) of every transition.

This wires up `RiskIncident`, a table that existed in the V1 schema but
that nothing ever read or wrote (see docs/V1_AUDIT.md §2/§11) — it is not
a new table, it's a table that finally has a real owner.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.phase5 import RiskIncident, IncidentEvent
from app.models.sos import SOSAlert
from app.models.trip import Trip
from app.models.user import User, UserRole


class IncidentStatus:
    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    ASSESSING = "assessing"
    RESCUE_DISPATCHED = "rescue_dispatched"
    RESCUE_IN_PROGRESS = "rescue_in_progress"
    SAFE = "safe"
    CLOSED = "closed"
    CANCELLED = "cancelled"

    ALL = {RECEIVED, ACKNOWLEDGED, ASSESSING, RESCUE_DISPATCHED, RESCUE_IN_PROGRESS, SAFE, CLOSED, CANCELLED}
    TERMINAL = {CLOSED, CANCELLED}
    OPEN = ALL - TERMINAL


LEGAL_TRANSITIONS: dict[str, set[str]] = {
    IncidentStatus.RECEIVED: {IncidentStatus.ACKNOWLEDGED, IncidentStatus.CANCELLED},
    IncidentStatus.ACKNOWLEDGED: {IncidentStatus.ASSESSING, IncidentStatus.RESCUE_DISPATCHED, IncidentStatus.CANCELLED},
    IncidentStatus.ASSESSING: {IncidentStatus.RESCUE_DISPATCHED, IncidentStatus.SAFE, IncidentStatus.CANCELLED},
    IncidentStatus.RESCUE_DISPATCHED: {IncidentStatus.RESCUE_IN_PROGRESS, IncidentStatus.CANCELLED},
    IncidentStatus.RESCUE_IN_PROGRESS: {IncidentStatus.SAFE, IncidentStatus.CANCELLED},
    IncidentStatus.SAFE: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
    IncidentStatus.CANCELLED: set(),
}


class IncidentService:
    @staticmethod
    def create_from_sos(db: Session, sos_alert: SOSAlert) -> RiskIncident:
        """Auto-creates an incident the moment an SOS is received — this is
        the system-generated first event in the timeline, actor=None."""
        existing = db.query(RiskIncident).filter(RiskIncident.sos_alert_id == sos_alert.id).first()
        if existing:
            return existing

        incident = RiskIncident(
            trip_id=sos_alert.trip_id,
            sos_alert_id=sos_alert.id,
            fisherman_id=sos_alert.user_id,
            incident_type=sos_alert.alert_type or "UNKNOWN",
            severity="critical",
            description=sos_alert.message,
            location_json=f'{{"lat": {sos_alert.latitude}, "lng": {sos_alert.longitude}}}',
            status=IncidentStatus.RECEIVED,
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        db.add(IncidentEvent(
            incident_id=incident.id,
            actor_id=None,
            previous_status=None,
            new_status=IncidentStatus.RECEIVED,
            reason="SOS alert received",
        ))
        db.commit()
        return incident

    @staticmethod
    def transition(
        db: Session,
        incident: RiskIncident,
        new_status: str,
        actor: User,
        reason: str | None = None,
    ) -> RiskIncident:
        if new_status not in IncidentStatus.ALL:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown incident status '{new_status}'")
        legal = LEGAL_TRANSITIONS.get(incident.status, set())
        if new_status not in legal:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Cannot transition incident from '{incident.status}' to '{new_status}'",
            )

        previous = incident.status
        incident.status = new_status
        now = datetime.now(timezone.utc)
        if new_status == IncidentStatus.ACKNOWLEDGED:
            incident.acknowledged_by = actor.id
            incident.acknowledged_at = now
        if new_status in IncidentStatus.TERMINAL or new_status == IncidentStatus.CLOSED:
            incident.closed_at = now
        if reason and new_status in (IncidentStatus.SAFE, IncidentStatus.CLOSED):
            incident.resolution = reason

        db.add(IncidentEvent(
            incident_id=incident.id,
            actor_id=actor.id,
            previous_status=previous,
            new_status=new_status,
            reason=reason,
        ))
        db.commit()
        db.refresh(incident)
        return incident

    @staticmethod
    def get_active(db: Session, skip: int = 0, limit: int = 100) -> list[RiskIncident]:
        return (
            db.query(RiskIncident)
            .filter(RiskIncident.status.in_(IncidentStatus.OPEN))
            .order_by(RiskIncident.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_timeline(db: Session, incident_id: int) -> list[IncidentEvent]:
        return (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at.asc())
            .all()
        )

    @staticmethod
    def authorize_view(db: Session, incident: RiskIncident, user: User) -> None:
        """Operator sees everything; the fisherman involved and their linked
        family can see their own incident. Raises 403 otherwise."""
        if user.role == UserRole.operator:
            return
        if incident.fisherman_id == user.id:
            return
        if user.role == UserRole.family:
            from app.models.family_link import FamilyLink
            linked = (
                db.query(FamilyLink)
                .filter(FamilyLink.family_user_id == user.id, FamilyLink.fisherman_id == incident.fisherman_id)
                .first()
            )
            if linked:
                return
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authorized to view this incident")

    @staticmethod
    def generate_report(db: Session, incident: RiskIncident) -> dict:
        """Structured incident report (docs/INCIDENT_ENGINE.md). Pulls only
        real, already-recorded data — never fabricates a field it doesn't
        have (missing fields are surfaced as null, not guessed)."""
        trip = db.query(Trip).filter(Trip.id == incident.trip_id).first() if incident.trip_id else None
        sos = db.query(SOSAlert).filter(SOSAlert.id == incident.sos_alert_id).first() if incident.sos_alert_id else None
        fisherman = db.query(User).filter(User.id == incident.fisherman_id).first() if incident.fisherman_id else None
        timeline = IncidentService.get_timeline(db, incident.id)

        return {
            "incident_id": incident.id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": incident.status,
            "severity": incident.severity,
            "incident_type": incident.incident_type,
            "fisherman": {"id": fisherman.id, "full_name": fisherman.full_name} if fisherman else None,
            "boat_name": fisherman.boat_name if fisherman else None,
            "trip": {"id": trip.id, "status": trip.status, "destination": trip.destination} if trip else None,
            "sos_alert": (
                {
                    "id": sos.id,
                    "alert_type": sos.alert_type,
                    "triggered_at": sos.triggered_at.isoformat() if sos.triggered_at else None,
                    "latitude": sos.latitude,
                    "longitude": sos.longitude,
                }
                if sos
                else None
            ),
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
            "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
            "resolution": incident.resolution,
            "timeline": [
                {
                    "timestamp": e.created_at.isoformat() if e.created_at else None,
                    "actor_id": e.actor_id,
                    "previous_status": e.previous_status,
                    "new_status": e.new_status,
                    "reason": e.reason,
                }
                for e in timeline
            ],
            "response_time_seconds": (
                (incident.acknowledged_at - incident.created_at).total_seconds()
                if incident.acknowledged_at and incident.created_at
                else None
            ),
        }
