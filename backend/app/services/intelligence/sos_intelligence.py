from sqlalchemy.orm import Session
from app.models.sos import SOSAlert
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext

class SOSIntelligenceService:
    @staticmethod
    def evaluate_sos_incident(db: Session, alert: SOSAlert) -> DecisionSupport:
        """
        Evaluate SOS severity, resources.
        """
        rules_triggered = []
        risk_level = "red"  # SOS is always at least red
        
        data = {
            "alert_type": alert.alert_type,
            "status": alert.status.value,
        }
        
        if alert.alert_type == "medical":
            rules_triggered.append("Medical emergency reported.")
            risk_level = "critical"
        elif alert.alert_type == "sinking":
            rules_triggered.append("Vessel sinking reported.")
            risk_level = "critical"
        else:
            rules_triggered.append(f"General SOS of type {alert.alert_type}.")

        context = IntelligenceContext(
            target_name=f"SOS Alert {alert.id}",
            context_type="SOS Incident Assessment",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
