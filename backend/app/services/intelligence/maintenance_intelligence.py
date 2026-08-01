from sqlalchemy.orm import Session
from app.models.boat import Boat
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext

class MaintenanceIntelligenceService:
    @staticmethod
    def evaluate_maintenance_needs(db: Session, boat: Boat) -> DecisionSupport:
        """
        Evaluate predictive maintenance, RUL (Remaining Useful Life), and failure probability.
        """
        rules_triggered = []
        risk_level = "green"
        
        # Mocking data for intelligence layer
        data = {
            "engine_operating_hours": 450,
            "hours_since_last_service": 150,
            "failure_probability_percent": 12,
            "remaining_useful_life_days": 180
        }

        if data["hours_since_last_service"] > 100:
            rules_triggered.append(f"Engine has run {data['hours_since_last_service']} hours since last service (threshold 100h).")
            risk_level = "yellow"
            
        if data["failure_probability_percent"] > 25:
            rules_triggered.append(f"Failure probability is high ({data['failure_probability_percent']}%).")
            risk_level = "red"

        context = IntelligenceContext(
            target_name=f"Boat {boat.id} Maintenance",
            context_type="Predictive Maintenance",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
