"""
Trip Readiness Service — determines whether a boat is safe to begin a fishing trip.

This service is one of the most important safety services inside OceanGuardian.
It never simply returns READY/NOT_READY. Instead it returns a structured safety
evaluation with scoring, blocking issues, warnings, passed checks, and recommendations.

Design principles:
  - Every evaluation is deterministic and explainable.
  - Future-ready: weather intelligence and AI risk scoring can be integrated
    later without redesigning the service.
  - Emergency SOS must NEVER be blocked — the service is only consulted for
    trip start, not for emergency response.
  - All checks are independent and additive — the safety score starts at 100
    and is reduced by weighted penalties.

Safety scoring weights:
  - Boat lifecycle status: 20 points
  - Crew readiness: 20 points
  - Documents compliance: 25 points
  - Equipment readiness: 20 points
  - Maintenance status: 15 points
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.boat import (
    Boat,
    BoatDocument,
    BoatEquipmentItem,
    BoatCrewMember,
    BoatInspection,
    BoatStatus,
    BoatVerificationStatus,
)
from app.repositories.boat_repository import BoatRepository

logger = logging.getLogger("app.services.boat_readiness")

# ── Constants ─────────────────────────────────────────────────────────────────
_MINIMUM_CREW_FOR_TRIP = 1        # at minimum, captain must be assigned
_SCORE_MAX = 100.0
_SCORE_BOAT_STATUS_WEIGHT = 20.0
_SCORE_CREW_WEIGHT = 20.0
_SCORE_DOCUMENTS_WEIGHT = 25.0
_SCORE_EQUIPMENT_WEIGHT = 20.0
_SCORE_MAINTENANCE_WEIGHT = 15.0

MANDATORY_EQUIPMENT_CATEGORIES = {
    "life_saving": ["life_jacket", "life_buoy", "life_raft"],
    "fire_safety": ["fire_extinguisher"],
    "communication": ["radio", "gps", "emergency_beacon"],
    "first_aid": ["first_aid_kit"],
    "navigation": ["compass", "navigation_lights"],
}

# Document types that must be valid (non-expired) for a trip
MANDATORY_DOCUMENT_TYPES = {
    "registration_certificate",
    "fishing_license",
    "insurance_policy",
}

# Statuses that are blocking for trip start
BLOCKING_BOAT_STATUSES = {
    BoatStatus.INACTIVE.value,
    BoatStatus.MAINTENANCE.value,
    BoatStatus.EMERGENCY.value,
    BoatStatus.LOST.value,
    BoatStatus.DAMAGED.value,
    BoatStatus.DECOMMISSIONED.value,
}


# =============================================================================
# Readiness Evaluation Data Classes
# =============================================================================

class ReadinessCheck:
    """A single readiness check result."""
    def __init__(self, name: str, passed: bool, message: str = "", severity: str = "info"):
        self.name = name
        self.passed = passed
        self.message = message
        self.severity = severity  # "blocking", "warning", "info"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
        }


class ReadinessEvaluation:
    """Complete readiness evaluation for a boat."""
    def __init__(
        self,
        boat_id: int,
        trip_allowed: bool = False,
        overall_status: str = "UNSAFE",
        safety_score: float = 0.0,
        blocking_issues: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
        passed_checks: Optional[list[str]] = None,
        recommendations: Optional[list[str]] = None,
        check_details: Optional[list[dict]] = None,
    ):
        self.boat_id = boat_id
        self.trip_allowed = trip_allowed
        self.overall_status = overall_status  # "SAFE", "CAUTION", "UNSAFE"
        self.safety_score = safety_score      # 0-100
        self.blocking_issues = blocking_issues or []
        self.warnings = warnings or []
        self.passed_checks = passed_checks or []
        self.recommendations = recommendations or []
        self.check_details = check_details or []

    def to_dict(self) -> dict:
        return {
            "boat_id": self.boat_id,
            "trip_allowed": self.trip_allowed,
            "overall_status": self.overall_status,
            "safety_score": round(self.safety_score, 1),
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "passed_checks": self.passed_checks,
            "recommendations": self.recommendations,
            "check_details": self.check_details,
        }

    def add_blocking_issue(self, issue: str):
        self.blocking_issues.append(issue)
        self.trip_allowed = False
        self.overall_status = "UNSAFE"

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def add_passed_check(self, check: str):
        self.passed_checks.append(check)

    def add_recommendation(self, recommendation: str):
        self.recommendations.append(recommendation)

    def add_check_detail(self, check: ReadinessCheck):
        self.check_details.append(check.to_dict())
        if not check.passed:
            if check.severity == "blocking":
                self.add_blocking_issue(check.message or check.name)
            elif check.severity == "warning":
                self.add_warning(check.message or check.name)
        else:
            self.add_passed_check(check.name)
        if check.message and check.severity == "info":
            self.add_recommendation(check.message)


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_document_expired(doc: BoatDocument) -> bool:
    """Check if a document is expired based on its expiry_date."""
    if doc.expiry_date is None:
        return False
    return doc.expiry_date < _now().date()


# =============================================================================
# Boat Readiness Service
# =============================================================================

class BoatReadinessService:
    """Determines whether a boat is safe to begin a fishing trip.

    All methods are ``@staticmethod`` consistent with the existing service-layer
    pattern (BoatService, CheckInService, BoatHealthService).

    Future integration points:
      - Weather intelligence: pass weather data to ``evaluate_boat_readiness``
        to factor sea conditions into the safety score.
      - AI risk scoring: integrate with RiskPredictionService for ML-based
        risk assessment (see RiskPrediction model).
    """

    # ── Main evaluation entry point ──────────────────────────────────────────

    @staticmethod
    def evaluate_boat_readiness(
        db: Session,
        boat_id: int,
        weather_data: Optional[dict] = None,
        ai_risk_score: Optional[float] = None,
    ) -> ReadinessEvaluation:
        """Perform a full safety evaluation of a boat for trip readiness.

        Returns a structured ``ReadinessEvaluation`` with:
          - ``trip_allowed``: boolean — whether the boat can start a trip
          - ``overall_status``: "SAFE", "CAUTION", or "UNSAFE"
          - ``safety_score``: 0-100 weighted score
          - ``blocking_issues``: issues that must be resolved before trip start
          - ``warnings``: non-blocking concerns
          - ``passed_checks``: checks that passed
          - ``recommendations``: suggestions for improvement
          - ``check_details``: detailed results of each individual check

        Args:
            db: Database session.
            boat_id: ID of the boat to evaluate.
            weather_data: Optional weather intelligence data for future integration.
            ai_risk_score: Optional AI risk score (0-100) for future integration.

        Returns:
            ReadinessEvaluation with full safety assessment.
        """
        logger.info("evaluate_boat_readiness started | boat_id=%s", boat_id)

        # Fetch boat (with deletion guard)
        boat = BoatRepository.get_by_id(db, boat_id)
        if boat is None:
            logger.warning("evaluate_boat_readiness boat not found | boat_id=%s", boat_id)
            return ReadinessEvaluation(
                boat_id=boat_id,
                overall_status="UNSAFE",
                safety_score=0.0,
                blocking_issues=["Boat not found or has been deleted"],
            )

        evaluation = ReadinessEvaluation(
            boat_id=boat_id,
            trip_allowed=True,
            overall_status="SAFE",
            safety_score=_SCORE_MAX,
        )

        # Run each check category — each mutates evaluation in-place
        BoatReadinessService._check_boat_status(boat, evaluation)
        BoatReadinessService._check_verification_status(boat, evaluation)
        BoatReadinessService._check_crew_readiness(db, boat_id, evaluation)
        BoatReadinessService._check_documents_compliance(db, boat_id, evaluation)
        BoatReadinessService._check_equipment_readiness(db, boat_id, evaluation)
        BoatReadinessService._check_maintenance_status(db, boat_id, evaluation)

        # Future integration: weather intelligence
        if weather_data is not None:
            BoatReadinessService._integrate_weather(weather_data, evaluation)

        # Future integration: AI risk scoring
        if ai_risk_score is not None:
            BoatReadinessService._integrate_ai_risk_score(ai_risk_score, evaluation)

        # Derive overall_status from safety_score
        if evaluation.safety_score >= 80.0 and evaluation.trip_allowed:
            evaluation.overall_status = "SAFE"
        elif evaluation.safety_score >= 50.0 and evaluation.trip_allowed:
            evaluation.overall_status = "CAUTION"
        else:
            evaluation.overall_status = "UNSAFE"

        logger.info(
            "evaluate_boat_readiness complete | boat_id=%s | trip_allowed=%s | "
            "score=%s | status=%s | blocking=%d | warnings=%d",
            boat_id, evaluation.trip_allowed, evaluation.safety_score,
            evaluation.overall_status, len(evaluation.blocking_issues),
            len(evaluation.warnings),
        )

        return evaluation

    # ── Individual check methods ─────────────────────────────────────────────

    @staticmethod
    def _check_boat_status(boat: Boat, evaluation: ReadinessEvaluation) -> None:
        """Check that the boat lifecycle state permits trip dispatch.

        Score weight: 20 points. Deductions:
          - Blocking status (inactive/maintenance/emergency/lost/damaged/decommissioned): -20
          - Soft-deleted: -20
          - is_active=False: -10 (warning)
        """
        check_name = "boat_lifecycle_status"

        # Soft-delete check
        if boat.deleted_at is not None:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=False,
                message="Boat has been deleted",
                severity="blocking",
            ))
            evaluation.safety_score -= _SCORE_BOAT_STATUS_WEIGHT
            return

        # Blocking status check
        if boat.status in BLOCKING_BOAT_STATUSES:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=False,
                message=f"Boat is in '{boat.status}' status — cannot start trip",
                severity="blocking",
            ))
            evaluation.safety_score -= _SCORE_BOAT_STATUS_WEIGHT
            return

        # is_active warning
        if not boat.is_active:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=True,
                message="Boat is marked inactive — consider reactivating before trip",
                severity="warning",
            ))
            evaluation.safety_score -= 10.0
            return

        evaluation.add_check_detail(ReadinessCheck(
            name=check_name,
            passed=True,
            message=f"Boat status is '{boat.status}' — OK",
            severity="info",
        ))

    @staticmethod
    def _check_verification_status(boat: Boat, evaluation: ReadinessEvaluation) -> None:
        """Check that the boat is verified.

        Verification is advisory (warning) not blocking — an unverified boat
        can still start a trip but should be flagged.
        Score weight: included in boat status weight as sub-check.
        """
        check_name = "boat_verification_status"

        if boat.verification_status == BoatVerificationStatus.VERIFIED.value:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=True,
                message="Boat is verified",
                severity="info",
            ))
        elif boat.verification_status == BoatVerificationStatus.REJECTED.value:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=True,
                message="Boat verification was rejected — operator may need to re-verify",
                severity="warning",
            ))
            evaluation.safety_score -= 5.0
        else:
            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=True,
                message=f"Boat verification status is '{boat.verification_status}' — "
                        f"operator verification recommended",
                severity="warning",
            ))
            evaluation.safety_score -= 3.0

    @staticmethod
    def _check_crew_readiness(db: Session, boat_id: int, evaluation: ReadinessEvaluation) -> None:
        """Check that the crew meets minimum requirements for trip dispatch.

        Score weight: 20 points. Deductions:
          - No captain assigned: -20 (blocking)
          - No active crew at all: -15
          - Less than minimum crew count: -10 (warning)
        """
        active_crew = BoatRepository.list_active_crew(db, boat_id)

        # No active crew at all — blocking
        if not active_crew:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_readiness",
                passed=False,
                message="No active crew members assigned to this boat",
                severity="blocking",
            ))
            evaluation.safety_score -= _SCORE_CREW_WEIGHT
            return

        # Captain check
        captain_count = sum(1 for m in active_crew if m.role == "captain")
        if captain_count == 0:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_captain_assigned",
                passed=False,
                message="No captain assigned to the boat — a captain is required",
                severity="blocking",
            ))
            evaluation.safety_score -= _SCORE_CREW_WEIGHT
            return

        if captain_count > 1:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_single_captain",
                passed=True,
                message=f"Multiple captains ({captain_count}) assigned — "
                        f"consider designating a single primary captain",
                severity="warning",
            ))
            evaluation.safety_score -= 3.0
        else:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_captain_assigned",
                passed=True,
                message=f"Captain assigned: {active_crew[0].full_name}",
                severity="info",
            ))

        # Minimum crew count
        if len(active_crew) < _MINIMUM_CREW_FOR_TRIP:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_minimum_count",
                passed=False,
                message=f"Minimum crew of {_MINIMUM_CREW_FOR_TRIP} required — "
                        f"only {len(active_crew)} assigned",
                severity="blocking",
            ))
            evaluation.safety_score -= 10.0
        else:
            evaluation.add_check_detail(ReadinessCheck(
                name="crew_minimum_count",
                passed=True,
                message=f"{len(active_crew)} crew members assigned",
                severity="info",
            ))

    @staticmethod
    def _check_documents_compliance(db: Session, boat_id: int, evaluation: ReadinessEvaluation) -> None:
        """Check that all mandatory documents are present and not expired.

        Score weight: 25 points. Deductions:
          - Each missing mandatory document: -10 (blocking)
          - Each expired mandatory document: -10 (blocking)
          - Expiring within 30 days: -3 (warning) per document
        """
        documents = BoatRepository.list_documents(db, boat_id)

        # Check each mandatory document type
        for doc_type in MANDATORY_DOCUMENT_TYPES:
            check_name = f"document_{doc_type}"

            # Find documents of this type
            matching_docs = [d for d in documents if d.document_type == doc_type]

            if not matching_docs:
                evaluation.add_check_detail(ReadinessCheck(
                    name=check_name,
                    passed=False,
                    message=f"Mandatory document '{doc_type}' is missing",
                    severity="blocking",
                ))
                evaluation.safety_score -= 10.0
                continue

            # Check the most recently issued document of this type
            latest_doc = max(matching_docs, key=lambda d: d.issue_date or d.created_at)

            if _is_document_expired(latest_doc):
                evaluation.add_check_detail(ReadinessCheck(
                    name=check_name,
                    passed=False,
                    message=f"'{doc_type}' expired on {latest_doc.expiry_date}",
                    severity="blocking",
                ))
                evaluation.safety_score -= 10.0
                continue

            # Check if expiring soon (within 30 days)
            if latest_doc.expiry_date is not None:
                days_until_expiry = (latest_doc.expiry_date - _now().date()).days
                if 0 <= days_until_expiry <= 30:
                    evaluation.add_check_detail(ReadinessCheck(
                        name=check_name,
                        passed=True,
                        message=f"'{doc_type}' expires in {days_until_expiry} days "
                                f"({latest_doc.expiry_date}) — renew soon",
                        severity="warning",
                    ))
                    evaluation.safety_score -= 3.0
                    continue

            evaluation.add_check_detail(ReadinessCheck(
                name=check_name,
                passed=True,
                message=f"'{doc_type}' is valid",
                severity="info",
            ))

    @staticmethod
    def _check_equipment_readiness(db: Session, boat_id: int, evaluation: ReadinessEvaluation) -> None:
        """Check that mandatory safety equipment is present and in good condition.

        Score weight: 20 points. Deductions:
          - Each mandatory item missing: -5 (blocking) per category
          - Each mandatory item in poor/missing condition: -3 (warning) per item
        """
        equipment = BoatRepository.list_equipment(db, boat_id)

        for category, required_items in MANDATORY_EQUIPMENT_CATEGORIES.items():
            category_name = f"equipment_{category}"
            category_items = [e for e in equipment if e.category == category]

            missing_items = []
            poor_items = []

            for item_name in required_items:
                matching = [e for e in category_items if e.item_name == item_name]
                if not matching:
                    missing_items.append(item_name)
                else:
                    item = matching[0]
                    if item.condition in ("poor", "missing"):
                        poor_items.append(item_name)

            if missing_items:
                evaluation.add_check_detail(ReadinessCheck(
                    name=category_name,
                    passed=False,
                    message=f"Missing mandatory {category} equipment: {', '.join(missing_items)}",
                    severity="blocking",
                ))
                evaluation.safety_score -= 5.0
            elif poor_items:
                evaluation.add_check_detail(ReadinessCheck(
                    name=category_name,
                    passed=True,
                    message=f"Equipment in poor condition: {', '.join(poor_items)} "
                            f"— repair or replace before trip",
                    severity="warning",
                ))
                evaluation.safety_score -= 3.0
            else:
                evaluation.add_check_detail(ReadinessCheck(
                    name=category_name,
                    passed=True,
                    message=f"All {category} equipment is present and in good condition",
                    severity="info",
                ))

    @staticmethod
    def _check_maintenance_status(db: Session, boat_id: int, evaluation: ReadinessEvaluation) -> None:
        """Check for overdue or failed maintenance/inspections.

        Score weight: 15 points. Deductions:
          - Critical inspection failure: -15 (blocking)
          - Overdue inspection (past due date): -10 (blocking)
          - Upcoming due date within 7 days: -5 (warning)
        """
        inspections = BoatRepository.list_inspections(db, boat_id)

        if not inspections:
            evaluation.add_check_detail(ReadinessCheck(
                name="maintenance_inspections",
                passed=True,
                message="No inspection records found — schedule an inspection",
                severity="warning",
            ))
            evaluation.safety_score -= 3.0
            return

        # Check for critical failures
        failed_inspections = [i for i in inspections if i.result == "failed"]
        if failed_inspections:
            latest_failed = max(failed_inspections, key=lambda i: i.inspection_date)
            evaluation.add_check_detail(ReadinessCheck(
                name="maintenance_no_critical_failures",
                passed=False,
                message=f"Critical inspection failure: {latest_failed.inspection_type} "
                        f"on {latest_failed.inspection_date} — {latest_failed.findings or 'no details'}",
                severity="blocking",
            ))
            evaluation.safety_score -= _SCORE_MAINTENANCE_WEIGHT
            return

        # Check for overdue next_due_date
        today = _now().date()
        overdue = [i for i in inspections if i.next_due_date and i.next_due_date < today]
        if overdue:
            most_overdue = min(overdue, key=lambda i: i.next_due_date)
            evaluation.add_check_detail(ReadinessCheck(
                name="maintenance_overdue",
                passed=False,
                message=f"Overdue inspection: {most_overdue.inspection_type} "
                        f"was due on {most_overdue.next_due_date}",
                severity="blocking",
            ))
            evaluation.safety_score -= 10.0
            return

        # Check upcoming due dates (within 7 days)
        from datetime import timedelta
        upcoming = [
            i for i in inspections
            if i.next_due_date and i.next_due_date >= today
            and i.next_due_date <= today + timedelta(days=7)
        ]
        if upcoming:
            nearest = min(upcoming, key=lambda i: i.next_due_date)
            evaluation.add_check_detail(ReadinessCheck(
                name="maintenance_upcoming",
                passed=True,
                message=f"Upcoming inspection due: {nearest.inspection_type} "
                        f"on {nearest.next_due_date}",
                severity="warning",
            ))
            evaluation.safety_score -= 5.0
        else:
            evaluation.add_check_detail(ReadinessCheck(
                name="maintenance_status",
                passed=True,
                message="All maintenance and inspections are current",
                severity="info",
            ))

    # ── Future integration points ────────────────────────────────────────────

    @staticmethod
    def _integrate_weather(weather_data: dict, evaluation: ReadinessEvaluation) -> None:
        """Integrate weather intelligence into the readiness score.

        Args:
            weather_data: Weather dictionary with keys like 'sea_state',
                         'wind_speed_knots', 'wave_height_meters', etc.
            evaluation: The evaluation to update.

        Future implementers:
            - Pass weather data from WeatherService or OpenMeteo API.
            - Evaluate thresholds: wave height > 2m, wind > 20 knots, etc.
            - Add blocking_issues for unsafe conditions.
            - Add warnings for marginal conditions.
        """
        # Stub for future weather intelligence integration
        logger.info(
            "Weather intelligence integration point hit | boat_id=%s",
            evaluation.boat_id,
        )
        # Example implementation (commented out until weather schema is finalised):
        # sea_state = weather_data.get("sea_state", "unknown")
        # wave_height = weather_data.get("wave_height_meters", 0)
        # wind_speed = weather_data.get("wind_speed_knots", 0)
        #
        # if wave_height > 3.0:
        #     evaluation.add_check_detail(ReadinessCheck(
        #         name="weather_sea_state",
        #         passed=False,
        #         message=f"Wave height {wave_height}m exceeds safe limit of 3m",
        #         severity="blocking",
        #     ))
        #     evaluation.safety_score -= 15.0
        # elif wave_height > 2.0:
        #     evaluation.add_check_detail(ReadinessCheck(
        #         name="weather_sea_state",
        #         passed=True,
        #         message=f"Wave height {wave_height}m — caution advised",
        #         severity="warning",
        #     ))
        #     evaluation.safety_score -= 5.0
        pass

    @staticmethod
    def _integrate_ai_risk_score(ai_risk_score: float, evaluation: ReadinessEvaluation) -> None:
        """Integrate AI-based risk scoring into readiness evaluation.

        Args:
            ai_risk_score: AI-generated risk score (0 = low risk, 100 = high risk).
            evaluation: The evaluation to update.

        Future implementers:
            - Pass risk score from RiskPredictionService.
            - Scores > 70: block the trip.
            - Scores 40-70: add warning.
        """
        # Stub for future AI risk scoring integration
        logger.info(
            "AI risk score integration point hit | boat_id=%s | score=%s",
            evaluation.boat_id, ai_risk_score,
        )
        # Example implementation:
        # if ai_risk_score > 70:
        #     evaluation.add_check_detail(ReadinessCheck(
        #         name="ai_risk_assessment",
        #         passed=False,
        #         message=f"AI risk score {ai_risk_score}/100 exceeds safe threshold",
        #         severity="blocking",
        #     ))
        #     evaluation.safety_score -= 20.0
        # elif ai_risk_score > 40:
        #     evaluation.add_check_detail(ReadinessCheck(
        #         name="ai_risk_assessment",
        #         passed=True,
        #         message=f"AI risk score {ai_risk_score}/100 — moderate risk detected",
        #         severity="warning",
        #     ))
        #     evaluation.safety_score -= 10.0
        pass
