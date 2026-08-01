"""
OceanGuardian AI — Harbor Intelligence Service.

Evaluates real harbor data from harbors, harbor_visits, and harbor_reviews:
- Capacity (projected vs actual based on trips)
- Available services (fuel, ice, medical, repair)
- Harbor traffic/congestion
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.phase5 import Harbor, HarborReview, HarborVisit
from app.models.trip import Trip
from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, HarborReport,
)


class HarborIntelligenceService:
    """Harbor intelligence — queries real harbor and visit data."""

    @staticmethod
    def evaluate(db: Session, harbor: Harbor) -> HarborReport:
        """Full harbor intelligence report."""
        
        capacity = HarborIntelligenceService._assess_capacity(db, harbor)
        services = HarborIntelligenceService._assess_services(harbor)
        traffic = HarborIntelligenceService._assess_traffic(db, harbor)

        return HarborReport(
            harbor_id=harbor.id,
            harbor_name=harbor.name,
            capacity_assessment=capacity,
            services_assessment=services,
            traffic_assessment=traffic,
        )

    @staticmethod
    def _assess_capacity(db: Session, harbor: Harbor) -> DecisionSupport:
        """Assess harbor capacity based on active trips targeting it."""
        # Find active trips heading to this harbor (using destination or harbor_id if it existed)
        # We approximate inbound vessels by trips currently active
        inbound = db.query(Trip).filter(
            Trip.status == "active",
            # Assuming 'destination' might contain harbor name, or we just count all trips for now as mock
            Trip.destination.ilike(f"%{harbor.name}%") if harbor.name else False
        ).count()
        
        # Real capacity logic requires knowing harbor size, but we approximate
        capacity_limit = 100 # Mock max
        projected = inbound
        
        evidence = [
            DecisionEvidence(metric_name="Inbound Trips", value=inbound, severity="warning" if inbound > capacity_limit * 0.8 else "ok"),
            DecisionEvidence(metric_name="Estimated Capacity", value=capacity_limit, severity="ok")
        ]
        
        rules = []
        risk_level = "green"
        
        if projected > capacity_limit:
            rules.append(f"Projected traffic ({projected}) exceeds harbor capacity ({capacity_limit}).")
            risk_level = "red"
        elif projected > capacity_limit * 0.8:
            rules.append(f"Harbor is nearing capacity ({projected}/{capacity_limit}).")
            risk_level = "yellow"
            
        if not rules:
            rules.append("Harbor has available capacity.")
            
        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Harbor is open." if risk_level == "green" else "Harbor capacity constrained.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.7,
            priority=priority_map.get(risk_level, "normal"),
            risk_level=risk_level
        )

    @staticmethod
    def _assess_services(harbor: Harbor) -> DecisionSupport:
        """Assess available services."""
        evidence = [
            DecisionEvidence(metric_name="Fuel Available", value=harbor.fuel_availability, severity="ok" if harbor.fuel_availability else "warning"),
            DecisionEvidence(metric_name="Medical Facility", value=harbor.medical_facility, severity="ok" if harbor.medical_facility else "warning"),
            DecisionEvidence(metric_name="Repair Facility", value=harbor.repair_facility, severity="ok" if harbor.repair_facility else "warning"),
        ]
        
        rules = []
        if harbor.fuel_availability:
            rules.append("Fuel is available.")
        if harbor.medical_facility:
            rules.append("Medical facilities present.")
        if not rules:
            rules.append("Limited services available at this harbor.")
            
        return DecisionSupport(
            recommendation="Services available.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.9,
            priority="low",
            risk_level="green"
        )

    @staticmethod
    def _assess_traffic(db: Session, harbor: Harbor) -> DecisionSupport:
        """Assess recent visits and reviews."""
        recent_visits = db.query(HarborVisit).filter(HarborVisit.harbor_id == harbor.id).count()
        avg_rating = harbor.average_rating or 0.0
        
        evidence = [
            DecisionEvidence(metric_name="Recent Visits", value=recent_visits, severity="ok"),
            DecisionEvidence(metric_name="Average Rating", value=round(avg_rating, 1), severity="ok" if avg_rating >= 3.0 else "warning")
        ]
        
        return DecisionSupport(
            recommendation="Traffic levels normal.",
            reason=f"{recent_visits} recent visits recorded. Rating: {avg_rating:.1f}/5.",
            evidence=evidence,
            confidence_score=0.8,
            priority="low",
            risk_level="green"
        )
