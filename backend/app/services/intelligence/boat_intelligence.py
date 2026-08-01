from sqlalchemy.orm import Session
from app.models.boat import Boat
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext

class BoatIntelligenceService:
    @staticmethod
    def evaluate_boat_health(db: Session, boat: Boat) -> DecisionSupport:
        """
        Evaluate boat engine health, fuel efficiency, and battery health.
        """
        # In a real system, we'd query metrics from telemetry tables.
        # For this prototype, we'll use deterministic rules on the boat model or mock data.
        
        rules_triggered = []
        data = {
            "engine_type": boat.engine_type or "Unknown",
            "is_active": boat.is_active
        }
        risk_level = "green"

        if not boat.is_active:
            rules_triggered.append("Boat is marked inactive.")
            risk_level = "yellow"

        # Mock telemetry evaluation (since telemetry model might not exist or be populated)
        data["battery_voltage"] = 12.4
        data["fuel_efficiency_gph"] = 4.5
        
        if data["battery_voltage"] < 11.5:
            rules_triggered.append("Low battery voltage detected.")
            risk_level = "red"
        
        context = IntelligenceContext(
            target_name=f"Boat {boat.id} ({boat.name})",
            context_type="Boat Health Evaluation",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
