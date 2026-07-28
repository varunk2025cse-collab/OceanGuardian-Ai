"""
Live Weather Intelligence — v2 (docs/WEATHER_INTELLIGENCE.md).

Distinct from /api/v1/weather/active (the static, manually-seeded hazard
advisory table used for the risk-score radius lookup): this endpoint calls
a real weather provider for live current conditions at a point. See
app.services.weather_service for the provider abstraction.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.services.weather_service import get_weather_provider

router = APIRouter(prefix="/api/v2/weather", tags=["weather-intelligence"])


class LiveWeatherOut(BaseModel):
    latitude: float
    longitude: float
    source: str
    timestamp: str
    available: bool
    wind_speed_kmh: float | None
    wind_direction_deg: float | None
    wave_height_m: float | None
    wave_direction_deg: float | None
    precipitation_mm: float | None
    pressure_hpa: float | None
    visibility_m: float | None
    unavailable_reason: str | None


@router.get("/live", response_model=LiveWeatherOut)
def get_live_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: User = Depends(get_current_user),
):
    obs = get_weather_provider().fetch(lat, lon)
    return LiveWeatherOut(
        latitude=obs.latitude,
        longitude=obs.longitude,
        source=obs.source,
        timestamp=obs.timestamp,
        available=obs.available,
        wind_speed_kmh=obs.wind_speed_kmh,
        wind_direction_deg=obs.wind_direction_deg,
        wave_height_m=obs.wave_height_m,
        wave_direction_deg=obs.wave_direction_deg,
        precipitation_mm=obs.precipitation_mm,
        pressure_hpa=obs.pressure_hpa,
        visibility_m=obs.visibility_m,
        unavailable_reason=obs.unavailable_reason,
    )
