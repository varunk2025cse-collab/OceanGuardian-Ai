"""
Weather / marine hazard advisories.

MVP models a hazard zone as a simple circle (center lat/lon + radius_km)
rather than a full polygon, which is enough to drive the mobile alert
screen and is trivial to compute "am I inside this zone" against on-device
during offline mode using the last cached alert list.
"""
import enum
from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, Float, String, DateTime, Enum, Text, Boolean, func
from app.database import Base


class HazardSeverity(str, enum.Enum):
    advisory = "advisory"
    warning = "warning"
    danger = "danger"


class HazardType(str, enum.Enum):
    cyclone = "cyclone"
    high_waves = "high_waves"
    storm = "storm"
    strong_wind = "strong_wind"
    lightning = "lightning"


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=False)
    hazard_type = Column(String(50), nullable=True)
    severity = Column(String(20), nullable=False, index=True, default="advisory")
    
    region = Column(String(120), nullable=True)
    alert_type = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)

    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False, default=50)

    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(120), nullable=True)  # e.g. "INCOIS", "IMD"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __init__(self, *args, **kwargs):
        if "title" not in kwargs:
            kwargs["title"] = kwargs.get("name") or "Weather Alert"
        if "description" not in kwargs:
            kwargs["description"] = kwargs.get("message") or "Weather alert"
        if "center_latitude" not in kwargs:
            kwargs["center_latitude"] = kwargs.get("latitude", 0.0)
        if "center_longitude" not in kwargs:
            kwargs["center_longitude"] = kwargs.get("longitude", 0.0)
        if "radius_km" not in kwargs:
            kwargs["radius_km"] = kwargs.get("radius", 50.0)
        if "valid_from" not in kwargs:
            kwargs["valid_from"] = datetime.utcnow()
        if "valid_until" not in kwargs:
            kwargs["valid_until"] = datetime.utcnow() + timedelta(days=1)
        super().__init__(*args, **kwargs)
