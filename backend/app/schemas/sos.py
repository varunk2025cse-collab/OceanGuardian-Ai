from datetime import datetime
from pydantic import BaseModel, Field


# SOS 2.0 emergency taxonomy (docs/SOS_ARCHITECTURE.md). "MANUAL_SOS" is the
# default — the one-button press with no type selected — everything else is
# an explicit type the fisherman (or, in the future, hardware) selects.
EMERGENCY_TYPES = (
    "MANUAL_SOS",
    "MAN_OVERBOARD",
    "MEDICAL",
    "FIRE",
    "CAPSIZE",
    "COLLISION",
    "ENGINE_FAILURE",
    "SEVERE_WEATHER",
    "FUEL_SHORTAGE",
    "COMMUNICATION_FAILURE",
    "UNKNOWN",
)
_EMERGENCY_TYPE_PATTERN = "^(" + "|".join(EMERGENCY_TYPES) + ")$"


class SOSAlertIn(BaseModel):
    client_uuid: str = Field(..., min_length=8, max_length=36)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float | None = None
    battery_level_percent: int | None = Field(default=None, ge=0, le=100)
    network_type: str | None = Field(default=None, max_length=20)
    message: str | None = None
    alert_type: str = Field(default="MANUAL_SOS", pattern=_EMERGENCY_TYPE_PATTERN)
    triggered_at: datetime


class SOSAlertOut(BaseModel):
    id: int
    client_uuid: str
    user_id: int
    trip_id: int | None
    latitude: float
    longitude: float
    accuracy_meters: float | None
    battery_level_percent: int | None
    network_type: str | None = None
    message: str | None
    alert_type: str | None
    status: str
    priority: str | None          # Phase 2
    rescue_notes: str | None      # Phase 2
    acknowledged_by: int | None   # Phase 2
    acknowledged_at: datetime | None
    resolved_by: int | None       # Phase 2
    triggered_at: datetime
    received_at: datetime
    resolved_at: datetime | None
    resolved_note: str | None

    model_config = {"from_attributes": True}


class SOSStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|acknowledged|resolved|false_alarm)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    rescue_notes: str | None = None
    resolved_note: str | None = None
