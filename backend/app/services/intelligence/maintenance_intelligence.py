"""
OceanGuardian AI — Maintenance Intelligence Service.

Evaluates real maintenance records from boat_maintenance table:
- Overdue scheduled maintenance
- Predictive failure probability based on service history
- Remaining Useful Life (RUL) estimation
- Maintenance priority ranking
"""
from datetime import date, datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.boat import Boat
from app.models.phase5 import BoatHealthStatus, BoatMaintenance
from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, MaintenanceReport,
)

# Standard service intervals (days)
_SERVICE_INTERVALS = {
    "oil_change": 90,
    "filter_replacement": 180,
    "engine_servicing": 365,
    "hull_cleaning": 180,
    "propeller_check": 90,
    "electrical_check": 365,
}


class MaintenanceIntelligenceService:
    """Predictive maintenance — queries real service records."""

    @staticmethod
    def evaluate(db: Session, boat: Boat) -> MaintenanceReport:
        """Full maintenance intelligence report."""
        today = date.today()
        now = datetime.now(timezone.utc)

        records = db.query(BoatMaintenance).filter(
            BoatMaintenance.boat_id == boat.id,
        ).order_by(BoatMaintenance.scheduled_date.desc()).all()

        health = db.query(BoatHealthStatus).filter(BoatHealthStatus.boat_id == boat.id).first()

        overdue_items: List[DecisionSupport] = []
        upcoming_items: List[DecisionSupport] = []

        # Group by maintenance_type to find last completed
        last_completed = {}
        for r in records:
            mt = (r.maintenance_type or "unknown").lower()
            if r.completed_date and mt not in last_completed:
                last_completed[mt] = r

        # Check each standard service interval
        for service_type, interval_days in _SERVICE_INTERVALS.items():
            last = last_completed.get(service_type)
            if last and last.completed_date:
                last_date = last.completed_date.date() if isinstance(last.completed_date, datetime) else last.completed_date
                days_since = (today - last_date).days
                next_due = last_date + timedelta(days=interval_days)
                days_until = (next_due - today).days

                if days_until < 0:
                    overdue_items.append(DecisionSupport(
                        recommendation=f"Overdue: {service_type.replace('_', ' ').title()} — {abs(days_until)} days past due.",
                        reason=f"Last completed on {last_date}. Due every {interval_days} days.",
                        evidence=[
                            DecisionEvidence(metric_name="Days Since Service", value=days_since, threshold=interval_days, unit="days", severity="danger"),
                            DecisionEvidence(metric_name="Days Overdue", value=abs(days_until), unit="days", severity="danger"),
                        ],
                        confidence_score=0.95,
                        priority="high" if abs(days_until) < 30 else "critical",
                        risk_level="red" if abs(days_until) < 30 else "critical",
                        suggested_action=f"Schedule {service_type.replace('_', ' ')} immediately.",
                    ))
                elif days_until <= 30:
                    upcoming_items.append(DecisionSupport(
                        recommendation=f"Upcoming: {service_type.replace('_', ' ').title()} due in {days_until} days.",
                        reason=f"Last completed on {last_date}. Next due: {next_due}.",
                        evidence=[
                            DecisionEvidence(metric_name="Days Until Due", value=days_until, threshold=30, unit="days", severity="warning"),
                        ],
                        confidence_score=0.9,
                        priority="normal",
                        risk_level="yellow",
                        suggested_action=f"Plan {service_type.replace('_', ' ')} before {next_due}.",
                    ))

        # Check for pending/scheduled but not completed maintenance
        pending = [r for r in records if r.status in ("scheduled", "pending") and not r.completed_date]
        overdue_scheduled = [r for r in pending if r.scheduled_date and (
            (r.scheduled_date.date() if isinstance(r.scheduled_date, datetime) else r.scheduled_date) < today
        )]

        for r in overdue_scheduled:
            sched_date = r.scheduled_date.date() if isinstance(r.scheduled_date, datetime) else r.scheduled_date
            overdue_items.append(DecisionSupport(
                recommendation=f"Scheduled maintenance '{r.maintenance_type}' was due {sched_date} but not completed.",
                reason=f"Status: {r.status}. {r.description or ''}",
                evidence=[DecisionEvidence(metric_name="Scheduled Date", value=str(sched_date), severity="danger")],
                confidence_score=0.95,
                priority="high",
                risk_level="red",
                suggested_action=f"Complete or reschedule '{r.maintenance_type}'.",
            ))

        # Failure risk estimation
        failure_evidence: List[DecisionEvidence] = []
        failure_probability = 5  # base %

        if health and health.engine_hours:
            failure_evidence.append(DecisionEvidence(metric_name="Engine Hours", value=health.engine_hours, unit="hours", severity="ok"))
            if health.engine_hours > 3000:
                failure_probability += 15
            elif health.engine_hours > 1500:
                failure_probability += 5

        failure_probability += len(overdue_items) * 10
        failure_probability = min(failure_probability, 95)

        failure_risk_level = "green"
        if failure_probability > 60:
            failure_risk_level = "critical"
        elif failure_probability > 40:
            failure_risk_level = "red"
        elif failure_probability > 20:
            failure_risk_level = "yellow"

        failure_evidence.append(DecisionEvidence(
            metric_name="Estimated Failure Probability", value=failure_probability,
            threshold=20, unit="%", severity=failure_risk_level,
        ))

        # RUL estimation (simplified)
        rul_days = max(30, 365 - (len(overdue_items) * 60) - (failure_probability * 2))
        failure_evidence.append(DecisionEvidence(
            metric_name="Estimated Remaining Useful Life", value=rul_days,
            unit="days", severity="ok" if rul_days > 180 else "warning",
        ))

        failure_risk = DecisionSupport(
            recommendation=f"Failure probability: {failure_probability}%. RUL: ~{rul_days} days.",
            reason=f"Based on {len(records)} maintenance records, {len(overdue_items)} overdue items, and engine telemetry.",
            evidence=failure_evidence,
            confidence_score=0.7 if records else 0.3,
            priority={"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}[failure_risk_level],
            risk_level=failure_risk_level,
            suggested_action="Address overdue maintenance to reduce failure risk." if failure_probability > 20 else None,
        )

        # Overall urgency
        if overdue_items:
            urgency_level = "critical" if any(i.risk_level == "critical" for i in overdue_items) else "red"
            urgency_priority = "critical" if urgency_level == "critical" else "high"
            urgency_rec = f"{len(overdue_items)} maintenance item(s) overdue. Address immediately."
        elif upcoming_items:
            urgency_level = "yellow"
            urgency_priority = "normal"
            urgency_rec = f"{len(upcoming_items)} maintenance item(s) due within 30 days."
        else:
            urgency_level = "green"
            urgency_priority = "low"
            urgency_rec = "All maintenance is current."

        maintenance_urgency = DecisionSupport(
            recommendation=urgency_rec,
            reason=f"{len(overdue_items)} overdue, {len(upcoming_items)} upcoming, {len(records)} total records.",
            evidence=[
                DecisionEvidence(metric_name="Overdue Items", value=len(overdue_items), threshold=0, severity="danger" if overdue_items else "ok"),
                DecisionEvidence(metric_name="Upcoming Items", value=len(upcoming_items), severity="warning" if upcoming_items else "ok"),
                DecisionEvidence(metric_name="Total Records", value=len(records), severity="ok"),
            ],
            confidence_score=0.85 if records else 0.3,
            priority=urgency_priority,
            risk_level=urgency_level,
            suggested_action="Review overdue items in the maintenance queue." if overdue_items else None,
        )

        return MaintenanceReport(
            boat_id=boat.id,
            boat_name=boat.name,
            maintenance_urgency=maintenance_urgency,
            overdue_items=overdue_items,
            upcoming_items=upcoming_items,
            failure_risk=failure_risk,
        )
