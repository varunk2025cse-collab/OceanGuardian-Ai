"""
GPS location pings — extended for Phase 2, then for the V2 core build.

New column (Phase 2):
  trip_id : nullable FK to trips.id. NULL for pings recorded before Trip
            Management was introduced (backward-compatible). Once a fisherman
            starts a trip, new pings are tagged with that trip_id.

New columns (V2 core — GPS tracking Part 1/3):
  altitude_meters, battery_percent, network_type : optional device telemetry
            captured alongside the fix, nullable since older app builds and
            non-GPS sources won't always have them.
  source    : where this ping came from. Today only "MOBILE_GPS" is ever
              written. Deliberately a plain string (not a DB enum) so a
              future IoT device gateway or satellite adapter can start
              writing "IOT_DEVICE"/"SATELLITE" without a migration — the
              ingestion path just needs a new writer, not a schema change.
"""
import uuid
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class LocationPing(Base):
    __tablename__ = "location_pings"

    id = Column(Integer, primary_key=True, index=True)
    client_uuid = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)  # Phase 2

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    speed_mps = Column(Float, nullable=True)
    heading_degrees = Column(Float, nullable=True)
    altitude_meters = Column(Float, nullable=True)
    battery_percent = Column(Float, nullable=True)
    network_type = Column(String(20), nullable=True)
    source = Column(String(20), nullable=False, default="MOBILE_GPS", server_default="MOBILE_GPS")

    recorded_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="locations", foreign_keys=[user_id])
    trip = relationship("Trip", back_populates="location_pings")

    def __init__(self, *args, **kwargs):
        if "fisherman_id" in kwargs and "user_id" not in kwargs:
            kwargs["user_id"] = kwargs.pop("fisherman_id")
        if "timestamp" in kwargs and "recorded_at" not in kwargs:
            kwargs["recorded_at"] = kwargs.pop("timestamp")
        if "created_at" in kwargs and "recorded_at" not in kwargs:
            kwargs["recorded_at"] = kwargs.pop("created_at")
        if "client_uuid" not in kwargs:
            kwargs["client_uuid"] = str(uuid.uuid4())
        super().__init__(*args, **kwargs)
