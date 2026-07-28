"""
Weather Risk Engine — Phase 2.

Computes a per-position risk score from active weather alerts:
  score=0  green   safe        no active alerts in range
  score=1  yellow  moderate    only advisory-severity alerts in range
  score=2  red     dangerous   warning or danger alerts in range

Used by:
  - Flutter app to show a risk badge on the home dashboard
  - React Rescue Dashboard to colour-code each fisherman on the map
  - The admin fishermen list (/api/v1/admin/fishermen)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.weather_alert import WeatherAlert
from app.schemas.admin import RiskScore
from app.schemas.weather import WeatherAlertOut
from app.services.geo import haversine_km

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


def compute_risk(lat: float, lon: float, db: Session) -> dict:
    """Pure function — also called by the admin router to annotate fishermen."""
    now = datetime.now(timezone.utc)
    all_active = (
        db.query(WeatherAlert)
        .filter(WeatherAlert.valid_from <= now, WeatherAlert.valid_until >= now)
        .all()
    )
    nearby = [
        a for a in all_active
        if haversine_km(lat, lon, a.center_latitude, a.center_longitude) <= a.radius_km
    ]

    if any(a.severity in ("warning", "danger") for a in nearby):
        score, label, color = 2, "dangerous", "red"
    elif any(a.severity == "advisory" for a in nearby):
        score, label, color = 1, "moderate", "yellow"
    else:
        score, label, color = 0, "safe", "green"

    return {
        "score": score,
        "label": label,
        "color": color,
        "alerts": [WeatherAlertOut.model_validate(a) for a in nearby],
    }


@router.get("/score", response_model=RiskScore)
def get_risk_score(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the risk level for a given GPS position based on active weather alerts.
    Called by the Flutter app for the home dashboard risk badge.
    """
    return compute_risk(lat, lon, db)
