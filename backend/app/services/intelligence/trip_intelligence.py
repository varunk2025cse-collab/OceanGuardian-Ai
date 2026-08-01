from sqlalchemy.orm import Session
from app.models.trip import Trip
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext

class TripIntelligenceService:
    @staticmethod
    def evaluate_trip_risk(db: Session, trip: Trip) -> DecisionSupport:
        """
        Evaluate trip risk, delay detection, etc.
        """
        rules_triggered = []
        risk_level = "green"
        
        data = {
            "destination": trip.destination,
            "status": trip.status,
            "delay_detected": False,
            "night_navigation_required": False
        }

        # Mock delay detection
        if trip.status == "in_progress":
            data["delay_detected"] = True
            rules_triggered.append("Trip is running behind estimated return time.")
            risk_level = "yellow"

        context = IntelligenceContext(
            target_name=f"Trip {trip.id}",
            context_type="Trip Risk Assessment",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
