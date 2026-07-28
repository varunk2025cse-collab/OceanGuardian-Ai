"""Risk prediction schemas."""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class RiskFactors(BaseModel):
    """Risk contributing factors."""
    weather_risk: float = 0.0
    distance_from_harbor_km: float = 0.0
    gps_stale_minutes: int = 0
    missed_checkins: int = 0
    trip_duration_hours: float = 0.0
    boat_health_score: float = 100.0
    fuel_remaining_percent: float = 100.0
    sos_history_count: int = 0
    time_of_day_risk: float = 0.0


class RiskPredictionResponse(BaseModel):
    """Risk prediction response."""
    risk_level: str  # SAFE, WATCH, WARNING, CRITICAL
    risk_score: float  # 0-100
    factors: Dict[str, float]
    reasons: List[str]
    recommended_action: str
    confidence: float
    missed_checkins_considered: bool = False


class TripRiskResponse(BaseModel):
    """Trip risk assessment."""
    trip_id: int
    fisherman_id: int
    fisherman_name: str
    risk_level: str
    risk_score: float
    last_updated: datetime
    factors: Dict[str, float]
    recommendations: List[str]
    missed_checkin_risk: Optional[float] = None


class HighRiskBoat(BaseModel):
    """High-risk boat information."""
    boat_id: int
    boat_name: str
    registration_number: str
    fisherman_id: int
    fisherman_name: str
    trip_id: Optional[int]
    risk_level: str
    risk_score: float
    primary_risks: List[str]
    last_location: Optional[Dict[str, float]]
    missed_checkin_count: int = 0


class RiskRecalculateRequest(BaseModel):
    """Request to recalculate risk."""
    trip_id: Optional[int] = None
    fisherman_id: Optional[int] = None
    force_update: bool = False
