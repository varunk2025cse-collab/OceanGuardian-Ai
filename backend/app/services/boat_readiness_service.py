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

        # Fetch boa
