from sqlalchemy.orm import Session
from app.models.boat import Boat
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext
from datetime import datetime, timezone

class EquipmentIntelligenceService:
    @staticmethod
    def evaluate_equipment_readiness(db: Session, boat: Boat) -> DecisionSupport:
        """
        Evaluate equipment expiry and missing items.
        """
        rules_triggered = []
        risk_level = "green"
        
        # In reality we'd check boat.equipment relationships
        # Mocking for Phase 4 implementation layer demonstration
        data = {
            "total_equipment_items": 15,
            "expired_items": 0,
            "missing_mandatory": 0
        }

        # Let's pretend there's 1 expired item
        data["expired_items"] = 1
        
        if data["missing_mandatory"] > 0:
            rules_triggered.append(f"{data['missing_mandatory']} mandatory items are missing.")
            risk_level = "critical"
        elif data["expired_items"] > 0:
            rules_triggered.append(f"{data['expired_items']} items are expired.")
            risk_level = "yellow"

        context = IntelligenceContext(
            target_name=f"Boat {boat.id} Equipment",
            context_type="Equipment Readiness",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
