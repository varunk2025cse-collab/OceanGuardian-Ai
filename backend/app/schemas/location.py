from datetime import datetime
from pydantic import BaseModel, Field


class LocationPingIn(BaseModel):
    """One GPS fix, as captured offline on the device."""
    client_uuid: str = Field(..., min_length=8, max_length=36)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float | None = None
    speed_mps: float | None = None
    heading_degrees: float | None = None
    altitude_meters: float | None = None
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    network_type: str | None = Field(default=None, max_length=20)
    # Only "MOBILE_GPS" is meaningful today. Kept open (not a DB enum) so a
    # future IoT/satellite ingestion path can populate this without a
    # schema migration; the mobile app always sends "MOBILE_GPS".
    source: str = Field(default="MOBILE_GPS", max_length=20)
    recorded_at: datetime


class LocationBatchSync(BaseModel):
    """The mobile app uploads queued offline points in a single batch on reconnect."""
    points: list[LocationPingIn]


class LocationOut(BaseModel):
    id: int
    client_uuid: str
    latitude: float
    longitude: float
    accuracy_meters: float | None
    speed_mps: float | None
    heading_degrees: float | None
    altitude_meters: float | None = None
    battery_percent: float | None = None
    network_type: str | None = None
    source: str = "MOBILE_GPS"
    recorded_at: datetime
    synced_at: datetime

    model_config = {"from_attributes": True}


class LocationSyncResult(BaseModel):
    accepted: int
    duplicates: int
    failed: int
