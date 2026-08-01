"""
OceanGuardian AI — Equipment Intelligence Service.

Evaluates real equipment inventory from boat_equipment_items table:
- Missing mandatory safety equipment
- Expired items
- Items in poor condition
- Replacement priority ranking
"""
from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.models.boat import Boat, BoatEquipmentItem
from app.schemas.intelligence import DecisionEvidence, DecisionSupport


# Indian maritime safety standards — minimum required equipment categories
MANDATORY_CATEGORIES = {
    "life_jacket": "Life Jackets",
    "fire_extinguisher": "Fire Extinguisher",
    "first_aid_kit": "First Aid Kit",
    "distress_signal": "Distress Signals / Flares",
    "navigation_light": "Navigation Lights",
    "anchor": "Anchor & Rope",
}

# Urgency weights for replacement priority
_URGENCY = {"expired": 3, "damaged": 3, "broken": 4, "poor": 2, "fair": 1}


class EquipmentIntelligenceService:
    """Equipment intelligence — queries real inventory data."""

    @staticmethod
    def evaluate(db: Session, boat: Boat) -> DecisionSupport:
        """Full equipment readiness assessment."""
        today = date.today()
        items = db.query(BoatEquipmentItem).filter(
            BoatEquipmentItem.boat_id == boat.id,
            BoatEquipmentItem.deleted_at.is_(None),
        ).all()

        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        total = len(items)
        expired = [i for i in items if i.expiry_date and i.expiry_date < today]
        poor = [i for i in items if i.condition in ("poor", "damaged", "broken")]

        # Check mandatory categories
        present_categories = set()
        for item in items:
            if item.category:
                present_categories.add(item.category.lower().strip())
        missing_mandatory = {k: v for k, v in MANDATORY_CATEGORIES.items() if k not in present_categories}

        evidence.append(DecisionEvidence(metric_name="Total Equipment Items", value=total, severity="ok"))

        if missing_mandatory:
            missing_names = ", ".join(missing_mandatory.values())
            evidence.append(DecisionEvidence(
                metric_name="Missing Mandatory Equipment", value=len(missing_mandatory),
                threshold=0, severity="danger",
            ))
            rules.append(f"CRITICAL: Missing mandatory safety equipment — {missing_names}.")
            risk_level = "critical"

        if expired:
            names = ", ".join(f"{i.item_name} (expired {i.expiry_date})" for i in expired[:5])
            evidence.append(DecisionEvidence(
                metric_name="Expired Equipment", value=len(expired),
                threshold=0, severity="danger",
            ))
            rules.append(f"{len(expired)} item(s) past expiry date: {names}.")
            risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if poor:
            names = ", ".join(f"{i.item_name} ({i.condition})" for i in poor[:5])
            evidence.append(DecisionEvidence(
                metric_name="Items in Poor Condition", value=len(poor),
                threshold=0, severity="warning",
            ))
            rules.append(f"{len(poor)} item(s) need replacement: {names}.")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        # Items expiring within 30 days (early warning)
        from datetime import timedelta
        expiring_soon = [
            i for i in items
            if i.expiry_date and today <= i.expiry_date <= today + timedelta(days=30)
        ]
        if expiring_soon:
            names = ", ".join(f"{i.item_name} ({i.expiry_date})" for i in expiring_soon[:3])
            evidence.append(DecisionEvidence(
                metric_name="Expiring Within 30 Days", value=len(expiring_soon),
                threshold=0, severity="warning",
            ))
            rules.append(f"{len(expiring_soon)} item(s) expiring soon: {names}.")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("All equipment is present, current, and in acceptable condition.")

        # Build replacement priority list
        replace_actions = []
        if missing_mandatory:
            replace_actions.append(f"Procure: {', '.join(missing_mandatory.values())}")
        if expired:
            replace_actions.append(f"Replace {len(expired)} expired item(s)")
        if poor:
            replace_actions.append(f"Repair/replace {len(poor)} damaged item(s)")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Equipment inventory is complete and serviceable." if risk_level == "green" else "Equipment issues must be resolved before next trip.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.95 if total > 0 else 0.2,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action="; ".join(replace_actions) if replace_actions else None,
            alternative_recommendations=["Contact nearest harbor with repair facility for procurement."] if risk_level != "green" else [],
        )
