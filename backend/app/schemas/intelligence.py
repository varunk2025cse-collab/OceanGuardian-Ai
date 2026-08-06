"""
OceanGuardian AI — Phase 4 Intelligence Layer Schemas.

Standardized Explainable AI (XAI) contracts that every intelligence module
MUST use for its outputs.  The core principle: **never return unexplained
predictions**.  Every recommendation carries the reason it was made, the
evidence that contributed, and a confidence score.

These schemas are the single source of truth for the JSON contract between
the intelligence layer and all consumers (REST API, Dashboard, Mobile).
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class DecisionEvidence(BaseModel):
    """A single piece of evidence that contributed to a decision."""
    metric_name: str = Field(description="Name of the metric or data point (e.g., 'Wind Speed')")
    value: Any = Field(description="The actual value observed")
    threshold: Optional[Any] = Field(None, description="The threshold it was compared against")
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., 'km/h', 'meters', 'days')")
    severity: Optional[str] = Field(None, description="How this evidence grades: 'ok', 'warning', 'danger'")


class DecisionSupport(BaseModel):
    """
    Standardized Explainable AI output.  Every intelligence module returns this.

    Design constraints:
    - Never return unexplained predictions
    - Every decision carries WHY, WHAT data contributed, WHICH rules triggered
    - Human-readable explanation for fishermen + structured data for dashboards
    """
    recommendation: str = Field(description="Clear, actionable recommendation")
    reason: str = Field(description="Human-readable explanation of why")
    evidence: List[DecisionEvidence] = Field(default_factory=list, description="Data points that drove this decision")
    confidence_score: float = Field(ge=0.0, le=1.0, description="0.0=no data, 1.0=certain")
    priority: str = Field(description="Priority: 'low', 'normal', 'high', 'critical'")
    risk_level: str = Field(description="Risk: 'green', 'yellow', 'red', 'critical'")
    suggested_action: Optional[str] = Field(None, description="Concrete next step")
    alternative_recommendations: List[str] = Field(default_factory=list, description="Alternatives if primary is not viable")


class BoatHealthReport(BaseModel):
    """Full boat health intelligence report."""
    boat_id: int
    boat_name: str
    overall_health: DecisionSupport
    engine_health: DecisionSupport
    document_compliance: DecisionSupport
    equipment_readiness: DecisionSupport
    inspection_status: DecisionSupport
    trip_readiness: DecisionSupport
    health_score: int = Field(ge=0, le=100, description="Composite 0-100 health score")


class TripRiskReport(BaseModel):
    """Full trip risk intelligence report."""
    trip_id: int
    fisherman_name: str
    overall_risk: DecisionSupport
    delay_assessment: DecisionSupport
    fuel_assessment: DecisionSupport
    weather_risk: Optional[DecisionSupport] = None
    risk_score: int = Field(ge=0, le=100, description="Composite 0-100 risk score")


class WeatherRiskReport(BaseModel):
    """Full weather risk intelligence report."""
    latitude: float
    longitude: float
    wind_risk: DecisionSupport
    wave_risk: DecisionSupport
    visibility_risk: DecisionSupport
    storm_risk: DecisionSupport
    overall_fishing_safety: DecisionSupport
    weather_confidence: float = Field(ge=0.0, le=1.0)


class MaintenanceReport(BaseModel):
    """Predictive maintenance intelligence report."""
    boat_id: int
    boat_name: str
    maintenance_urgency: DecisionSupport
    overdue_items: List[DecisionSupport] = Field(default_factory=list)
    upcoming_items: List[DecisionSupport] = Field(default_factory=list)
    failure_risk: DecisionSupport


class HarborReport(BaseModel):
    """Harbor intelligence report."""
    harbor_id: int
    harbor_name: str
    capacity_assessment: DecisionSupport
    services_assessment: DecisionSupport
    traffic_assessment: DecisionSupport


class SOSReport(BaseModel):
    """SOS incident intelligence report."""
    alert_id: int
    severity_assessment: DecisionSupport
    resource_recommendation: DecisionSupport
    response_priority: DecisionSupport
    estimated_rescue_minutes: Optional[int] = None

    # Tamil-language fields — populated for all responses, not just Tamil requests
    severity_reason_ta: Optional[str] = None
    resource_recommendation_ta: Optional[str] = None
    fisherman_message_ta: Optional[str] = None
    priority_label_ta: Optional[str] = None
    rescue_time_ta: Optional[str] = None
    status_ta: Optional[str] = None
