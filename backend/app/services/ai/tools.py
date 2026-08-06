"""
AI Tool Layer (docs/AI_TOOLS.md) — V2 core build Phase 18.

Every function here is a controlled, authorized, validated read against
the existing service layer. The AI layer (app.services.ai) — and the
Rescue AI panel endpoint that uses it — may ONLY reach data through these
functions. No tool executes raw SQL, no tool accepts an unvalidated
identifier without an authorization check, and no tool touches the
filesystem. This is what "AI must retrieve facts from controlled backend
tools, never direct DB access" means in code, not just in a docstring.

Every tool returns a plain dict (JSON-serializable, structured) — never a
free-text guess — and raises fastapi.HTTPException on authorization
failure exactly like the REST endpoints that wrap the same services.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.boat import Boat
from app.models.location import LocationPing
from app.models.phase5 import Harbor, RiskIncident
from app.models.sos import SOSAlert, SOSStatus
from app.models.trip import Trip
from app.models.user import User, UserRole
from app.routers.risk import compute_risk
from app.services.incident_service import IncidentService, IncidentStatus
from app.services.safety_engine import SafetyEngine
from app.services.trip_service import TripStatus
from app.services.tracking_service import TrackingService, compute_freshness


def _require_operator(user: User) -> None:
    if user.role != UserRole.operator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Operator role required for this tool")


def get_boat_status(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    _require_operator(requesting_user)
    boat = db.query(Boat).filter(Boat.owner_id == fisherman_id).first()
    if not boat:
        return {"found": False, "detail": "No boat on record for this fisherman."}
    return {
        "found": True,
        "boat_id": boat.id,
        "name": boat.name,
        "registration_number": boat.registration_number,
        "engine_type": boat.engine_type,
        "is_active": boat.is_active,
    }


def get_trip_status(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    _require_operator(requesting_user)
    trip = (
        db.query(Trip)
        .filter(Trip.user_id == fisherman_id, Trip.status.in_(TripStatus.IN_PROGRESS))
        .order_by(Trip.start_time.desc())
        .first()
    )
    if not trip:
        return {"found": False, "detail": "No trip currently in progress."}
    return {
        "found": True,
        "trip_id": trip.id,
        "status": trip.status,
        "start_time": trip.start_time.isoformat() if trip.start_time else None,
        "destination": trip.destination,
        "estimated_return_at": trip.estimated_return_at.isoformat() if trip.estimated_return_at else None,
    }


def get_latest_location(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    history = TrackingService.get_history(db, requesting_user, fisherman_id, limit=1)
    if not history:
        return {"found": False, "detail": "No location data available."}
    p = history[0]
    return {
        "found": True,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "recorded_at": p.recorded_at.isoformat(),
        "freshness": compute_freshness(p.recorded_at).value,
    }


def get_location_history(db: Session, requesting_user: User, fisherman_id: int, limit: int = 50) -> dict:
    history = TrackingService.get_history(db, requesting_user, fisherman_id, limit=limit)
    return {
        "count": len(history),
        "points": [{"latitude": p.latitude, "longitude": p.longitude, "recorded_at": p.recorded_at.isoformat()} for p in history],
    }


def get_location_freshness(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    result = get_latest_location(db, requesting_user, fisherman_id)
    if not result["found"]:
        return {"freshness": "UNKNOWN", "detail": "No location data."}
    return {"freshness": result["freshness"], "recorded_at": result["recorded_at"]}


def get_weather(db: Session, requesting_user: User, latitude: float, longitude: float) -> dict:
    from app.services.weather_service import get_weather_provider

    obs = get_weather_provider().fetch(latitude, longitude)
    return {
        "available": obs.available,
        "source": obs.source,
        "timestamp": obs.timestamp,
        "wind_speed_kmh": obs.wind_speed_kmh,
        "wave_height_m": obs.wave_height_m,
        "precipitation_mm": obs.precipitation_mm,
        "unavailable_reason": obs.unavailable_reason,
    }


def get_weather_alerts(db: Session, requesting_user: User, latitude: float, longitude: float) -> dict:
    risk = compute_risk(latitude, longitude, db)
    return {
        "alert_count": len(risk["alerts"]),
        "alerts": [{"title": a.title, "severity": a.severity, "hazard_type": a.hazard_type} for a in risk["alerts"]],
    }


def get_safety_state(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    _require_operator(requesting_user)
    fisherman = db.query(User).filter(User.id == fisherman_id).first()
    if not fisherman:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fisherman not found")
    ev = SafetyEngine.evaluate(db, fisherman)
    return {
        "safety_state": ev.safety_state,
        "safety_score": ev.safety_score,
        "communication_state": ev.communication_state,
        "freshness": ev.freshness,
        "reasons": ev.reasons,
        "trip_status": ev.trip_status,
    }


def get_risk_factors(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    return {"reasons": get_safety_state(db, requesting_user, fisherman_id)["reasons"]}


def get_active_incidents(db: Session, requesting_user: User) -> dict:
    _require_operator(requesting_user)
    incidents = IncidentService.get_active(db)
    return {
        "count": len(incidents),
        "incidents": [
            {"id": i.id, "status": i.status, "incident_type": i.incident_type, "fisherman_id": i.fisherman_id, "created_at": i.created_at.isoformat() if i.created_at else None}
            for i in incidents
        ],
    }


def get_incident(db: Session, requesting_user: User, incident_id: int) -> dict:
    incident = db.query(RiskIncident).filter(RiskIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")
    IncidentService.authorize_view(db, incident, requesting_user)
    return IncidentService.generate_report(db, incident)


def get_high_risk_vessels(db: Session, requesting_user: User) -> dict:
    _require_operator(requesting_user)
    fleet = TrackingService.get_fleet(db, limit=500)
    results = []
    for vessel in fleet:
        fisherman = db.query(User).filter(User.id == vessel.fisherman_id).first()
        if not fisherman:
            continue
        ev = SafetyEngine.evaluate(db, fisherman)
        if ev.safety_state in ("HIGH_RISK", "CRITICAL"):
            results.append({"fisherman_id": vessel.fisherman_id, "fisherman_name": vessel.fisherman_name, "safety_state": ev.safety_state, "safety_score": ev.safety_score})
    return {"count": len(results), "vessels": results}


def get_offline_vessels(db: Session, requesting_user: User) -> dict:
    _require_operator(requesting_user)
    fleet = TrackingService.get_fleet(db, limit=500)
    offline = [v for v in fleet if v.freshness.value in ("STALE", "UNKNOWN")]
    return {
        "count": len(offline),
        "vessels": [{"fisherman_id": v.fisherman_id, "fisherman_name": v.fisherman_name, "freshness": v.freshness.value} for v in offline],
    }


def get_active_sos(db: Session, requesting_user: User) -> dict:
    _require_operator(requesting_user)
    alerts = db.query(SOSAlert).filter(SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged])).all()
    return {
        "count": len(alerts),
        "alerts": [{"id": a.id, "user_id": a.user_id, "alert_type": a.alert_type, "status": a.status.value, "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None} for a in alerts],
    }


def get_navigation_guidance(db: Session, requesting_user: User, fisherman_id: int) -> dict:
    """Navigation AI (docs/NAVIGATION_AI.md): straight-line bearing and
    distance from a fisherman's last known position to the nearest known
    safe harbor. Same self/operator/linked-family authorization as
    get_latest_location — this is fisherman-facing guidance, not an
    operator-only tool."""
    location = get_latest_location(db, requesting_user, fisherman_id)
    if not location["found"]:
        return {"found": False, "detail": "No location data available to compute navigation guidance."}

    from app.services.harbor import HarborService

    nearest = HarborService.find_nearest_harbors(
        db, location["latitude"], location["longitude"], max_distance_km=200, limit=1
    )
    if not nearest:
        return {"found": True, "harbor_found": False, "detail": "No known harbor within range."}

    top = nearest[0]
    return {
        "found": True,
        "harbor_found": True,
        "harbor_name": top.harbor.name,
        "distance_km": top.distance_km,
        "bearing_degrees": top.bearing_degrees,
        "compass_direction": top.compass_direction,
        "estimated_minutes_to_reach": top.estimated_minutes_to_reach,
        "services_available": top.services_available,
    }


def get_rescue_resources(db: Session, requesting_user: User, latitude: float, longitude: float) -> dict:
    """Nearest harbors as a proxy for available rescue-staging resources —
    OceanGuardian does not model rescue vessels/personnel as of this
    build, so this deliberately returns harbor infrastructure only, not a
    fabricated resource roster."""
    _require_operator(requesting_user)
    from app.services.geo import haversine_km

    harbors = db.query(Harbor).all()
    scored = sorted(
        (
            {"name": h.name, "distance_km": haversine_km(latitude, longitude, h.latitude, h.longitude)}
            for h in harbors
            if h.latitude is not None and h.longitude is not None
        ),
        key=lambda x: x["distance_km"],
    )
    return {"nearest_harbors": scored[:5]}


def generate_incident_summary(db: Session, requesting_user: User, incident_id: int) -> dict:
    report = get_incident(db, requesting_user, incident_id)
    from app.services.ai.provider import get_ai_provider, ExplanationRequest

    reasons = [f"Incident type: {report['incident_type']}", f"Status: {report['status']}"]
    if report.get("response_time_seconds") is not None:
        reasons.append(f"Acknowledged in {report['response_time_seconds']:.0f}s")

    # Map incident lifecycle status to a safety state the provider understands.
    # Incident statuses (received/acknowledged/investigating/resolved/closed)
    # are NOT safety states — never pass them raw to ExplanationRequest.
    _incident_to_safety = {
        "received": "HIGH_RISK",
        "acknowledged": "CAUTION",
        "investigating": "CAUTION",
        "resolved": "SAFE",
        "closed": "SAFE",
    }
    safety_state = _incident_to_safety.get(
        (report.get("status") or "").lower(), "UNKNOWN"
    )

    req = ExplanationRequest(
        fisherman_name=(report.get("fisherman") or {}).get("full_name", "Unknown"),
        safety_state=safety_state,
        safety_score=0,
        communication_state="UNKNOWN",
        freshness="UNKNOWN",
        trip_status=(report.get("trip") or {}).get("status"),
        reasons=reasons,
    )
    text, provider_name = get_ai_provider().explain(req)
    return {"report": report, "summary": text, "summary_provider": provider_name}
