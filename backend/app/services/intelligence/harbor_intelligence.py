from sqlalchemy.orm import Session
from app.models.phase5 import Harbor
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext

class HarborIntelligenceService:
    @staticmethod
    def evaluate_harbor_capacity(db: Session, harbor: Harbor) -> DecisionSupport:
        """
        Evaluate harbor capacity, congestion.
        """
        rules_triggered = []
        risk_level = "green"
        
        data = {
            "capacity": harbor.capacity or 100,
            "current_vessels": 85,  # Mock
            "inbound_vessels": 20   # Mock
        }
        
        projected = data["current_vessels"] + data["inbound_vessels"]
        if projected > data["capacity"]:
            rules_triggered.append(f"Projected vessels ({projected}) exceed capacity ({data['capacity']}).")
            risk_level = "red"
        elif projected > data["capacity"] * 0.8:
            rules_triggered.append("Harbor is nearing capacity.")
            risk_level = "yellow"

        context = IntelligenceContext(
            target_name=f"Harbor {harbor.id} ({harbor.name})",
            context_type="Harbor Capacity Assessment",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
