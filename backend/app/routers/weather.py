"""
Weather / marine hazard alerts.

MVP serves alerts created by an admin/ops process (Stage 2: ingest from a
real provider like INCOIS/IMD or Open-Meteo marine API on a schedule). The
mobile app caches the full active list locally and re-evaluates "am I in a
hazard zone" against the GPS position even with zero connectivity.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.weather_alert import WeatherAlert
from app.schemas.weather import WeatherAlertOut
from app.services.geo import haversine_km

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.get("/active", response_model=list[WeatherAlertOut])
def list_active_alerts(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    All currently-valid alerts. If lat/lon is supplied (the boat's last known
    GPS fix), results are filtered to zones the boat actually sits inside,
    which is what the Weather Safety screen shows front and center.
    """
    now = datetime.now(timezone.utc)
    alerts = (
        db.query(WeatherAlert)
        .filter(WeatherAlert.valid_from <= now, WeatherAlert.valid_until >= now)
        .order_by(WeatherAlert.severity.desc())
        .all()
    )

    if lat is None or lon is None:
        return alerts

    return [
        a
        for a in alerts
        if haversine_km(lat, lon, a.center_latitude, a.center_longitude) <= a.radius_km
    ]
