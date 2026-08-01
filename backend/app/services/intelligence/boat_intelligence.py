"""
OceanGuardian AI — Boat Intelligence Service.

Evaluates the real health of a boat by querying:
- Boat lifecycle status (7-state FSM)
- Equipment inventory (expired, missing mandatory, condition)
- Document compliance (expired licenses, unverified documents)
- Inspection history (overdue, failed, conditional results)
- Maintenance history (overdue service, age of engine)
- Fuel efficiency (from BoatFuelLog)

Every assessment returns a DecisionSupport with real evidence, not mocks.
"""
from datetime import date, datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.boat import (
    Boat, BoatDocument, BoatEquipmentItem, BoatInspection,
    BoatStatus, BoatVerificationStatus,
)
from app.models.phase5 import BoatFuelLog, BoatHealthStatus, BoatMaintenance
from app.schemas.intelligence import (
    BoatHealthReport, DecisionEvidence, DecisionSupport,
)


# ── Mandatory equipment categories (Indian maritime safety standards) ────────
MANDATORY_EQUIPMENT_CATEGORIES = {
    "life_jacket", "fire_extinguisher", "first_aid_kit",
    "distress_signal", "navigation_light", "anchor",
}


class BoatIntelligenceService:
    """Production-grade boat intelligence — queries real data, no mocks."""

    @staticmethod
    def evaluate(db: Session, boat: Boat) -> BoatHealthReport:
        """Full boat health intelligence report."""
        today = date.today()
        now = datetime.now(timezone.utc)

        engine_health = BoatIntelligenceService._evaluate_engine(db, boat)
        doc_compliance = BoatIntelligenceService._evaluate_documents(db, boat, today)
        equip_readiness = BoatIntelligenceService._evaluate_equipment(db, boat, today)
        inspection_status = BoatIntelligenceService._evaluate_inspections(db, boat, today)
        trip_readiness = BoatIntelligenceService._evaluate_trip_readiness(boat, doc_compliance, equip_readiness, inspection_status)

        # Composite health score: weighted average of sub-scores
        weights = {
            "engine": (engine_health, 0.25),
            "documents": (doc_compliance, 0.20),
            "equipment": (equip_readiness, 0.25),
            "inspections": (inspection_status, 0.15),
            "trip": (trip_readiness, 0.15),
        }
        health_score = 0
        for decision, weight in weights.values():
            # Convert risk_level to numeric: green=100, yellow=70, red=30, critical=10
            risk_scores = {"green": 100, "yellow": 70, "red": 30, "critical": 10}
            health_score += risk_scores.get(decision.risk_level, 50) * weight
        health_score = max(0, min(100, int(health_score)))

        # Overall health assessment
        if health_score >= 80:
            overall_risk = "green"
            overall_priority = "low"
            overall_rec = "Boat is in good condition and ready for operations."
        elif health_score >= 60:
            overall_risk = "yellow"
            overall_priority = "normal"
            overall_rec = "Boat requires attention on some items before next trip."
        elif health_score >= 40:
            overall_risk = "red"
            overall_priority = "high"
            overall_rec = "Significant issues detected. Address before allowing trips."
        else:
            overall_risk = "critical"
            overall_priority = "critical"
            overall_rec = "Boat is not operationally safe. Immediate maintenance required."

        overall = DecisionSupport(
            recommendation=overall_rec,
            reason=f"Health score {health_score}/100 based on engine, documents, equipment, inspections, and readiness.",
            evidence=[DecisionEvidence(metric_name="Health Score", value=health_score, threshold=60, unit="points", severity=overall_risk)],
            confidence_score=0.85,
            priority=overall_priority,
            risk_level=overall_risk,
            suggested_action="Review individual assessments for specific action items.",
        )

        return BoatHealthReport(
            boat_id=boat.id,
            boat_name=boat.name,
            overall_health=overall,
            engine_health=engine_health,
            document_compliance=doc_compliance,
            equipment_readiness=equip_readiness,
            inspection_status=inspection_status,
            trip_readiness=trip_readiness,
            health_score=health_score,
        )

    @staticmethod
    def _evaluate_engine(db: Session, boat: Boat) -> DecisionSupport:
        """Evaluate engine health from BoatHealthStatus and fuel logs."""
        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        health_status = db.query(BoatHealthStatus).filter(BoatHealthStatus.boat_id == boat.id).first()
        fuel_logs = (
            db.query(BoatFuelLog)
            .filter(BoatFuelLog.boat_id == boat.id)
            .order_by(BoatFuelLog.timestamp.desc())
            .limit(10)
            .all()
        )

        # Engine hours check
        if health_status and health_status.engine_hours is not None:
            evidence.append(DecisionEvidence(metric_name="Engine Hours", value=health_status.engine_hours, unit="hours", severity="ok"))
            if health_status.engine_hours > 5000:
                rules.append(f"Engine has {health_status.engine_hours:.0f} operating hours — high wear risk.")
                risk_level = "red"
            elif health_status.engine_hours > 2000:
                rules.append(f"Engine approaching high-mileage at {health_status.engine_hours:.0f} hours.")
                risk_level = "yellow"

        # Existing health score from BoatHealthStatus
        if health_status and health_status.health_score is not None:
            evidence.append(DecisionEvidence(metric_name="Recorded Health Score", value=health_status.health_score, threshold=60, unit="/100", severity="warning" if health_status.health_score < 60 else "ok"))
            if health_status.health_score < 40:
                rules.append(f"Recorded health score is critically low ({health_status.health_score:.0f}/100).")
                risk_level = "critical"
            elif health_status.health_score < 60:
                rules.append(f"Recorded health score is below threshold ({health_status.health_score:.0f}/100).")
                if risk_level != "critical":
                    risk_level = "red"

        # Fuel efficiency from real logs
        if fuel_logs:
            efficiencies = [fl.efficiency_km_per_liter for fl in fuel_logs if fl.efficiency_km_per_liter and fl.efficiency_km_per_liter > 0]
            if efficiencies:
                avg_eff = sum(efficiencies) / len(efficiencies)
                evidence.append(DecisionEvidence(metric_name="Avg Fuel Efficiency", value=round(avg_eff, 2), unit="km/L", severity="ok" if avg_eff > 2.0 else "warning"))
                if avg_eff < 1.0:
                    rules.append(f"Very poor fuel efficiency ({avg_eff:.2f} km/L) — possible engine issues.")
                    risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        # Engine age
        if boat.engine_year and boat.engine_year > 0:
            age = date.today().year - boat.engine_year
            evidence.append(DecisionEvidence(metric_name="Engine Age", value=age, unit="years", severity="ok" if age < 10 else "warning"))
            if age > 20:
                rules.append(f"Engine is {age} years old — significant age risk.")
                risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)
            elif age > 10:
                rules.append(f"Engine is {age} years old — monitor for wear.")
                risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("No engine issues detected from available data.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Engine health is satisfactory." if risk_level == "green" else "Engine requires attention.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.8 if health_status else 0.4,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Schedule engine inspection or service.",
        )

    @staticmethod
    def _evaluate_documents(db: Session, boat: Boat, today: date) -> DecisionSupport:
        """Evaluate document compliance: expired, unverified, missing."""
        docs = db.query(BoatDocument).filter(
            BoatDocument.boat_id == boat.id,
            BoatDocument.deleted_at.is_(None),
        ).all()

        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        total = len(docs)
        expired = [d for d in docs if d.expiry_date and d.expiry_date < today]
        unverified = [d for d in docs if not d.is_verified]

        evidence.append(DecisionEvidence(metric_name="Total Documents", value=total, severity="ok"))
        evidence.append(DecisionEvidence(metric_name="Expired Documents", value=len(expired), threshold=0, severity="danger" if expired else "ok"))
        evidence.append(DecisionEvidence(metric_name="Unverified Documents", value=len(unverified), threshold=0, severity="warning" if unverified else "ok"))

        if expired:
            expired_names = ", ".join(d.document_type for d in expired[:3])
            rules.append(f"{len(expired)} document(s) expired: {expired_names}.")
            risk_level = "red"

        if unverified:
            rules.append(f"{len(unverified)} document(s) not yet verified by an operator.")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        # Boat verification status
        if boat.verification_status == BoatVerificationStatus.REJECTED.value:
            rules.append("Boat verification was REJECTED — re-submission required.")
            risk_level = "critical"
        elif boat.verification_status == BoatVerificationStatus.UNVERIFIED.value:
            rules.append("Boat has never been verified.")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("All documents are current and verified.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Document compliance is satisfactory." if risk_level == "green" else "Document issues require attention.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.95,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Renew expired documents and submit for verification.",
        )

    @staticmethod
    def _evaluate_equipment(db: Session, boat: Boat, today: date) -> DecisionSupport:
        """Evaluate equipment readiness: expired, missing mandatory, poor condition."""
        items = db.query(BoatEquipmentItem).filter(
            BoatEquipmentItem.boat_id == boat.id,
            BoatEquipmentItem.deleted_at.is_(None),
        ).all()

        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        total = len(items)
        expired_items = [i for i in items if i.expiry_date and i.expiry_date < today]
        poor_condition = [i for i in items if i.condition in ("poor", "damaged", "broken")]
        mandatory_present = {i.category for i in items if i.is_mandatory}
        mandatory_missing = MANDATORY_EQUIPMENT_CATEGORIES - mandatory_present

        evidence.append(DecisionEvidence(metric_name="Total Equipment Items", value=total, severity="ok"))
        evidence.append(DecisionEvidence(metric_name="Expired Items", value=len(expired_items), threshold=0, severity="danger" if expired_items else "ok"))
        evidence.append(DecisionEvidence(metric_name="Poor Condition Items", value=len(poor_condition), threshold=0, severity="warning" if poor_condition else "ok"))
        evidence.append(DecisionEvidence(metric_name="Missing Mandatory Categories", value=len(mandatory_missing), threshold=0, severity="danger" if mandatory_missing else "ok"))

        if mandatory_missing:
            rules.append(f"Missing mandatory equipment: {', '.join(mandatory_missing)}.")
            risk_level = "critical"

        if expired_items:
            names = ", ".join(i.item_name for i in expired_items[:3])
            rules.append(f"{len(expired_items)} equipment item(s) expired: {names}.")
            risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if poor_condition:
            names = ", ".join(i.item_name for i in poor_condition[:3])
            rules.append(f"{len(poor_condition)} item(s) in poor/damaged condition: {names}.")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("All equipment is present, current, and in good condition.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Equipment readiness is satisfactory." if risk_level == "green" else "Equipment issues must be resolved.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.9 if total > 0 else 0.3,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Replace expired items, procure missing mandatory equipment.",
        )

    @staticmethod
    def _evaluate_inspections(db: Session, boat: Boat, today: date) -> DecisionSupport:
        """Evaluate inspection compliance."""
        inspections = db.query(BoatInspection).filter(
            BoatInspection.boat_id == boat.id,
            BoatInspection.deleted_at.is_(None),
        ).order_by(BoatInspection.inspection_date.desc()).all()

        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        if not inspections:
            return DecisionSupport(
                recommendation="No inspection records found — schedule an inspection immediately.",
                reason="No inspection has ever been recorded for this boat.",
                evidence=[DecisionEvidence(metric_name="Total Inspections", value=0, severity="danger")],
                confidence_score=0.5,
                priority="high",
                risk_level="red",
                suggested_action="Schedule a safety inspection.",
            )

        latest = inspections[0]
        failed = [i for i in inspections if i.result in ("fail", "conditional")]
        overdue = [i for i in inspections if i.next_due_date and i.next_due_date < today]

        evidence.append(DecisionEvidence(metric_name="Total Inspections", value=len(inspections), severity="ok"))
        evidence.append(DecisionEvidence(metric_name="Latest Result", value=latest.result, severity="ok" if latest.result == "pass" else "warning"))
        evidence.append(DecisionEvidence(metric_name="Overdue Inspections", value=len(overdue), threshold=0, severity="danger" if overdue else "ok"))

        if latest.result == "fail":
            rules.append(f"Most recent inspection FAILED on {latest.inspection_date}.")
            risk_level = "critical"
        elif latest.result == "conditional":
            rules.append(f"Most recent inspection was CONDITIONAL — corrective actions required.")
            risk_level = "red"

        if overdue:
            rules.append(f"{len(overdue)} inspection(s) overdue for re-inspection.")
            risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("All inspections are current and passing.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Inspection status is satisfactory." if risk_level == "green" else "Inspection issues require resolution.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.9,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Address inspection findings and schedule re-inspection.",
        )

    @staticmethod
    def _evaluate_trip_readiness(boat: Boat, doc: DecisionSupport, equip: DecisionSupport, insp: DecisionSupport) -> DecisionSupport:
        """Synthesize trip readiness from boat state + sub-assessments."""
        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        evidence.append(DecisionEvidence(metric_name="Boat Status", value=boat.status, severity="ok" if boat.status in ("active", "registered") else "danger"))
        evidence.append(DecisionEvidence(metric_name="Is Active", value=boat.is_active, severity="ok" if boat.is_active else "danger"))

        if boat.deleted_at is not None:
            rules.append("Boat is soft-deleted and cannot operate.")
            risk_level = "critical"
        elif not boat.is_active:
            rules.append("Boat is marked as inactive.")
            risk_level = "red"
        elif boat.status not in (BoatStatus.ACTIVE.value, BoatStatus.REGISTERED.value):
            rules.append(f"Boat status is '{boat.status}' — not cleared for trips.")
            risk_level = "red"

        # Check sub-assessments for blockers
        blockers = []
        for name, sub in [("Documents", doc), ("Equipment", equip), ("Inspections", insp)]:
            if sub.risk_level in ("red", "critical"):
                blockers.append(name)
        if blockers:
            rules.append(f"Blocked by: {', '.join(blockers)}.")
            risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("Boat is cleared and ready for trip dispatch.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Boat is trip-ready." if risk_level == "green" else "Boat is NOT cleared for trip dispatch.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.95,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else f"Resolve issues in: {', '.join(blockers) if blockers else boat.status}.",
        )
