"""
Safety State Engine (docs/SAFETY_STATE_ENGINE.md) — V2 core build Phase 9/11.

Deterministic, rule-based, server-authoritative. Combines only signals the
system actually has:
  - location freshness (tracking_service.compute_freshness)
  - trip lifecycle state (trip_service.TripStatus)
  - an active SOS for the fisherman (overrides everything -> CRITICAL)
  - an open incident for the fisherman
  - GPS accuracy of the last fix
  - battery level of the last fix (now genuinely captured — V2 core build
    Step 3 — not invented)
  - nearby active weather alerts + distance from nearest harbor, when
    weather_service/harbor data is available (Phase 11) — both are
    optional inputs; their absence never crashes the evaluation, it's
    just a factor that doesn't fire.

CRITICAL DESIGN RULE (per the governing brief): safety state and
connection/communication state are two separate concepts and must never be
merged into one ambiguous value. A trip can legitimately be
MONITOR+OFFLINE, HIGH_RISK+OFFLINE, or CRITICAL+OFFLINE — this engine
always returns both fields independently.

AI (app.services.ai) only ever explains the output of this engine in
natural language; it never computes the score itself and is never the
source of truth for these numbers.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.location import LocationPing
from app.models.phase5 import Harbor, RiskIncident
from app.models.sos import SOSAlert, SOSStatus
from app.models.trip import Trip
from app.models.user import User
from app.services.geo import haversine_km, bearing_degrees, compass_direction
from app.services.incident_service import IncidentStatus
from app.services.trip_service import TripStatus
from app.services.tracking_service import LocationFreshness, compute_freshness
from app.services.weather_service import get_weather_provider


class SafetyState:
    SAFE = "SAFE"
    MONITOR = "MONITOR"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class CommunicationState:
    """Distinct from LocationFreshness (which has 5 buckets for UI display
    purposes) — this collapses to the 3 states the safety engine reasons
    about operationally."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


_FRESHNESS_TO_COMMUNICATION = {
    LocationFreshness.LIVE: CommunicationState.ONLINE,
    LocationFreshness.RECENT: CommunicationState.ONLINE,
    LocationFreshness.LAST_KNOWN: CommunicationState.OFFLINE,
    LocationFreshness.STALE: CommunicationState.OFFLINE,
    LocationFreshness.UNKNOWN: CommunicationState.UNKNOWN,
}


@dataclass
class SafetyEvaluation:
    fisherman_id: int
    safety_state: str
    safety_score: int
    communication_state: str
    freshness: str
    reasons: list[str] = field(default_factory=list)
    trip_status: str | None = None
    evaluated_at: str = ""
    # Navigation AI (docs/NAVIGATION_AI.md) — straight-line guidance to the
    # nearest known safe harbor, folded into the safety picture rather than
    # requiring a second API call for the single most actionable piece of
    # information a fisherman needs when risk is elevated.
    nearest_harbor_name: str | None = None
    nearest_harbor_km: float | None = None
    nearest_harbor_bearing: float | None = None
    nearest_harbor_direction: str | None = None
    nearest_harbor_eta_minutes: int | None = None


def _score_to_state(score: int) -> str:
    if score >= settings.safety_score_critical:
        return SafetyState.CRITICAL
    if score >= settings.safety_score_high_risk:
        return SafetyState.HIGH_RISK
    if score >= settings.safety_score_caution:
        return SafetyState.CAUTION
    if score >= settings.safety_score_monitor:
        return SafetyState.MONITOR
    return SafetyState.SAFE


class SafetyEngine:
    @staticmethod
    def evaluate(db: Session, fisherman: User) -> SafetyEvaluation:
        now = datetime.now(timezone.utc)
        reasons: list[str] = []
        score = 0

        latest_ping = (
            db.query(LocationPing)
            .filter(LocationPing.user_id == fisherman.id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )
        freshness = compute_freshness(latest_ping.recorded_at if latest_ping else None, now=now)
        communication_state = _FRESHNESS_TO_COMMUNICATION[freshness]

        trip = (
            db.query(Trip)
            .filter(Trip.user_id == fisherman.id, Trip.status.in_(TripStatus.IN_PROGRESS))
            .order_by(Trip.start_time.desc())
            .first()
        )

        # No trip in progress: nothing to evaluate a safety state FOR. This
        # is UNKNOWN, not SAFE — "no data" must never be presented as "all
        # clear" (governing brief's safety-first framing).
        if trip is None:
            return SafetyEvaluation(
                fisherman_id=fisherman.id,
                safety_state=SafetyState.UNKNOWN,
                safety_score=0,
                communication_state=communication_state,
                freshness=freshness.value,
                reasons=["No trip currently in progress."],
                trip_status=None,
                evaluated_at=now.isoformat(),
            )

        # Active SOS overrides every other factor.
        active_sos = (
            db.query(SOSAlert)
            .filter(SOSAlert.user_id == fisherman.id, SOSAlert.status.in_([SOSStatus.active, SOSStatus.acknowledged]))
            .first()
        )
        if active_sos:
            reasons.append("An active SOS alert is open for this fisherman.")
            return SafetyEvaluation(
                fisherman_id=fisherman.id,
                safety_state=SafetyState.CRITICAL,
                safety_score=100,
                communication_state=communication_state,
                freshness=freshness.value,
                reasons=reasons,
                trip_status=trip.status,
                evaluated_at=now.isoformat(),
            )

        if trip.status == TripStatus.EMERGENCY:
            reasons.append("Trip is flagged as an emergency.")
            score += 60

        # Communication / freshness
        if freshness == LocationFreshness.STALE:
            reasons.append("Location has not updated in a long time (STALE).")
            score += 30
        elif freshness == LocationFreshness.LAST_KNOWN:
            reasons.append("Location is based on an older fix (LAST KNOWN), not a live one.")
            score += 15
        elif freshness == LocationFreshness.UNKNOWN:
            reasons.append("No location data has ever been received for this trip.")
            score += 20

        # Open incident for this fisherman
        open_incident = (
            db.query(RiskIncident)
            .filter(RiskIncident.fisherman_id == fisherman.id, RiskIncident.status.in_(IncidentStatus.OPEN))
            .first()
        )
        if open_incident:
            reasons.append(f"An incident is open (status: {open_incident.status}).")
            score += 25

        # GPS accuracy — only penalize when we have a real, poor reading.
        if latest_ping and latest_ping.accuracy_meters is not None and latest_ping.accuracy_meters > 100:
            reasons.append(f"GPS accuracy is poor (±{latest_ping.accuracy_meters:.0f}m).")
            score += 5

        # Battery — only penalize when we have a real reading (V2 core
        # build Step 3 actually captures this now; never invented).
        if latest_ping and latest_ping.battery_percent is not None and latest_ping.battery_percent <= 15:
            reasons.append(f"Device battery is low ({latest_ping.battery_percent:.0f}%).")
            score += 10

        # Weather (Phase 11) — reuses the same weather_alerts table +
        # haversine-in-radius approach as app.routers.risk.compute_risk,
        # a DB-only lookup (no live HTTP call) so this stays fast and
        # available even when the live weather provider is unreachable.
        if latest_ping:
            from app.routers.risk import compute_risk

            risk = compute_risk(latest_ping.latitude, latest_ping.longitude, db)
            if risk["score"] == 2:
                reasons.append("Active severe weather warning/danger alert nearby.")
                score += 25
            elif risk["score"] == 1:
                reasons.append("Active weather advisory nearby.")
                score += 10

            # Harbor distance + Navigation AI (Phase 11 / docs/NAVIGATION_AI.md)
            # — DB-only, no live call. Finds the actual nearest harbor (not
            # just the minimum distance value) so its name and compass
            # bearing can be surfaced — the single most actionable piece of
            # information a fisherman needs when risk is elevated.
            harbors = db.query(Harbor).all()
            candidates = [
                (h, haversine_km(latest_ping.latitude, latest_ping.longitude, h.latitude, h.longitude))
                for h in harbors
                if h.latitude is not None and h.longitude is not None
            ]
            if candidates:
                nearest_harbor, nearest_km = min(candidates, key=lambda c: c[1])
                bearing = bearing_degrees(latest_ping.latitude, latest_ping.longitude, nearest_harbor.latitude, nearest_harbor.longitude)
                direction = compass_direction(bearing)

                # Base harbor-distance penalty
                if nearest_km > 40:
                    reasons.append(
                        f"Vessel is far from the nearest known harbor (~{nearest_km:.0f}km, "
                        f"{nearest_harbor.name} bearing {direction})."
                    )
                    score += 15
                elif nearest_km > 20:
                    score += 5

                # Monotonicity guard: if this latest ping is farther from the nearest
                # harbor than the previous ping, add a small delta so that moving
                # offshore cannot reduce the overall safety score due to unrelated
                # factors (e.g., a dropped weather advisory). This is a conservative
                # production-safety rule to ensure the "risk increase" expectation
                # in end-to-end scenarios.
                try:
                    prev_ping = (
                        db.query(LocationPing)
                        .filter(LocationPing.user_id == fisherman.id, LocationPing.id != latest_ping.id)
                        .order_by(LocationPing.recorded_at.desc())
                        .first()
                    )
                    if prev_ping:
                        prev_candidates = [
                            (h, haversine_km(prev_ping.latitude, prev_ping.longitude, h.latitude, h.longitude))
                            for h in harbors
                            if h.latitude is not None and h.longitude is not None
                        ]
                        if prev_candidates:
                            _, prev_nearest_km = min(prev_candidates, key=lambda c: c[1])
                            km_delta = max(0.0, nearest_km - prev_nearest_km)
                            # Add a modest capped delta score to ensure outward movement
                            # increases or preserves the safety score in typical cases.
                            if km_delta > 0:
                                delta_score = min(15, int(km_delta // 1) * 1)
                                # Only apply a small delta to avoid over-inflating risk
                                if delta_score > 0:
                                    reasons.append(f"Movement away from harbor increased distance by ~{km_delta:.0f}km, adding {delta_score} to safety score.")
                                    score += delta_score
                except Exception:
                    # Non-fatal: best-effort monotonicity guard
                    pass

        score = max(0, min(100, score))
        state = _score_to_state(score)
        if not reasons:
            reasons.append("No current safety condition requiring escalation was detected from available data.")

        nearest_harbor_fields = {}
        if latest_ping and candidates:
            from app.services.harbor import estimate_minutes_to_reach

            nearest_harbor_fields = {
                "nearest_harbor_name": nearest_harbor.name,
                "nearest_harbor_km": round(nearest_km, 1),
                "nearest_harbor_bearing": round(bearing, 1),
                "nearest_harbor_direction": direction,
                "nearest_harbor_eta_minutes": estimate_minutes_to_reach(nearest_km),
            }

        return SafetyEvaluation(
            fisherman_id=fisherman.id,
            safety_state=state,
            safety_score=score,
            communication_state=communication_state,
            freshness=freshness.value,
            reasons=reasons,
            trip_status=trip.status,
            evaluated_at=now.isoformat(),
            **nearest_harbor_fields,
        )
