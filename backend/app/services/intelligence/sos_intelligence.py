"""
OceanGuardian AI — SOS Intelligence Service.

Evaluates real SOS incidents:
- Severity of the alert (medical, sinking, piracy)
- Battery state of the vessel at time of distress
- GPS accuracy
- Recommended resources
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.sos import SOSAlert, SOSStatus
from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, SOSReport,
)


class SOSIntelligenceService:
    """SOS intelligence — queries real SOS data."""

    @staticmethod
    def evaluate(db: Session, alert: SOSAlert) -> SOSReport:
        """Full SOS intelligence report."""
        
        severity = SOSIntelligenceService._assess_severity(alert)
        resources = SOSIntelligenceService._recommend_resources(alert)
        priority = SOSIntelligenceService._assess_priority(alert)

        return SOSReport(
            alert_id=alert.id,
            severity_assessment=severity,
            resource_recommendation=resources,
            response_priority=priority,
            estimated_rescue_minutes=None # Would calculate from nearest harbor
        )

    @staticmethod
    def _assess_severity(alert: SOSAlert) -> DecisionSupport:
        """Assess severity based on alert type and conditions."""
        evidence = [
            DecisionEvidence(metric_name="Alert Type", value=alert.alert_type or "Unknown", severity="warning"),
            DecisionEvidence(metric_name="Battery Level", value=alert.battery_level_percent, unit="%", severity="danger" if alert.battery_level_percent and alert.battery_level_percent < 20 else "ok"),
            DecisionEvidence(metric_name="GPS Accuracy", value=alert.accuracy_meters, unit="m", severity="danger" if alert.accuracy_meters and alert.accuracy_meters > 100 else "ok"),
        ]
        
        rules = []
        risk_level = "red"
        
        if alert.alert_type == "medical":
            rules.append("Medical emergency reported — requires immediate medical assistance.")
            risk_level = "critical"
        elif alert.alert_type == "sinking":
            rules.append("Vessel sinking reported — life-threatening emergency.")
            risk_level = "critical"
        elif alert.alert_type == "piracy":
            rules.append("Piracy/hostile boarding reported — requires Coast Guard.")
            risk_level = "critical"
        else:
            rules.append(f"General SOS alert of type: {alert.alert_type or 'Unknown'}.")
            
        if alert.battery_level_percent and alert.battery_level_percent < 20:
            rules.append(f"Vessel battery is critically low ({alert.battery_level_percent}%). Communication may be lost soon.")
            
        return DecisionSupport(
            recommendation="Dispatch rescue resources immediately.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.95,
            priority="critical" if risk_level == "critical" else "high",
            risk_level=risk_level
        )

    @staticmethod
    def _recommend_resources(alert: SOSAlert) -> DecisionSupport:
        """Recommend rescue resources based on alert type."""
        evidence = [DecisionEvidence(metric_name="Alert Type", value=alert.alert_type or "Unknown", severity="warning")]
        
        if alert.alert_type == "medical":
            rec = "Dispatch Coast Guard medical vessel or air-evac."
        elif alert.alert_type == "sinking":
            rec = "Dispatch fast response rescue vessel and alert nearby fishing vessels."
        elif alert.alert_type == "piracy":
            rec = "Dispatch Coast Guard interceptor. Do not send unarmed civilian vessels."
        else:
            rec = "Dispatch standard search and rescue (SAR) vessel."
            
        return DecisionSupport(
            recommendation=rec,
            reason=f"Recommended based on incident type: {alert.alert_type or 'Unknown'}.",
            evidence=evidence,
            confidence_score=0.9,
            priority="high",
            risk_level="red"
        )
        
    @staticmethod
    def _assess_priority(alert: SOSAlert) -> DecisionSupport:
        """Assess operational priority."""
        status = alert.status
        if status == SOSStatus.resolved:
            return DecisionSupport(
                recommendation="Incident is resolved. No further action needed.",
                reason="Alert was marked resolved by operator.",
                evidence=[DecisionEvidence(metric_name="Status", value=status.value, severity="ok")],
                confidence_score=1.0,
                priority="low",
                risk_level="green"
            )
            
        return DecisionSupport(
            recommendation="Incident is ACTIVE. Immediate attention required.",
            reason=f"Alert status is {status.value}.",
            evidence=[DecisionEvidence(metric_name="Status", value=status.value, severity="danger")],
            confidence_score=1.0,
            priority="critical",
            risk_level="critical"
        )
