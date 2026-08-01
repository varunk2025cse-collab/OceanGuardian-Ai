from typing import Any, List, Optional
from pydantic import BaseModel, Field

class DecisionEvidence(BaseModel):
    """Specific piece of evidence supporting a decision."""
    metric_name: str = Field(description="Name of the metric or data point (e.g., 'Wind Speed')")
    value: Any = Field(description="The actual value observed")
    threshold: Optional[Any] = Field(None, description="The threshold it was compared against, if applicable")


class DecisionSupport(BaseModel):
    """
    Standardized Explainable AI output contract.
    Never return unexplained predictions.
    """
    recommendation: str = Field(description="The suggested action or prediction")
    reason: str = Field(description="Human readable explanation of why this was recommended")
    evidence: List[DecisionEvidence] = Field(default_factory=list, description="Data that contributed to this decision")
    confidence_score: float = Field(ge=0.0, le=1.0, description="0.0 to 1.0 confidence in this recommendation")
    priority: str = Field(description="Priority level (e.g., 'low', 'normal', 'high', 'critical')")
    risk_level: str = Field(description="Associated risk level (e.g., 'green', 'yellow', 'red', 'critical')")
    suggested_action: Optional[str] = Field(None, description="Actionable next step for the user or operator")
    alternative_recommendations: List[str] = Field(default_factory=list, description="Alternative options if primary is not viable")
