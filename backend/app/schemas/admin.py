"""
Schemas for operator-only admin endpoints consumed by the React Rescue Dashboard.
These return richer joined data than the fisherman-facing endpoints.
"""
from datetime import datetime
from pydantic import BaseModel
from app.schemas.user import UserOut
from app.schemas.location import LocationOut


class SOSAlertAdminOut(BaseModel):
    id: int
    client_uuid: str
    status: str
    priority: str | None
    rescue_notes: str | None
    triggered_at: datetime
    received_at: datetime
    resolved_at: datetime | None
    resolved_note: str | None
    latitude: float
    longitude: float
    accuracy_meters: float | None
    battery_level_percent: int | None
    message: str | None
    fisherman: UserOut
    acknowledged_by_user: UserOut | None = None
    resolved_by_user: UserOut | None = None

    model_config = {"from_attributes": True}


class ActiveTripSummary(BaseModel):
    id: int
    status: str
    start_time: datetime
    estimated_return_at: datetime | None
    destination: str | None
    boat_name: str | None = None

    model_config = {"from_attributes": True}


class FishermanAdminOut(BaseModel):
    id: int
    full_name: str
    phone_number: str
    boat_name: str | None
    boat_registration_number: str | None
    home_harbor: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    preferred_language: str
    last_location: LocationOut | None
    active_trip: ActiveTripSummary | None
    active_sos: bool
    risk_score: int    # 0=safe, 1=moderate, 2=dangerous — weather-proximity only, see app.routers.risk.compute_risk
    risk_label: str    # "safe", "moderate", "dangerous", or "unknown" (no location data — never "safe" by default)
    # Fuller signal from the Safety State Engine (docs/SAFETY_STATE_ENGINE.md)
    # — combines weather + freshness + trip state + incidents + battery,
    # not just weather proximity. Prefer this over risk_label in the UI.
    safety_state: str = "UNKNOWN"

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    active_sos_count: int
    active_trips_count: int
    fishermen_count: int
    critical_weather_count: int


class PaginatedSOS(BaseModel):
    items: list[SOSAlertAdminOut]
    total: int
    skip: int
    limit: int


class PaginatedFishermen(BaseModel):
    items: list[FishermanAdminOut]
    total: int
    skip: int
    limit: int


class RiskScore(BaseModel):
    score: int        # 0, 1, 2
    label: str        # "safe", "moderate", "dangerous"
    color: str        # "green", "yellow", "red"
    alerts: list      # active weather alerts affecting this position
