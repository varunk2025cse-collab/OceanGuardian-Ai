"""
OceanGuardian AI — Trip Intelligence Service.

Evaluates real trip data:
- Trip risk score based on duration, weather, distance, time of day
- Delay detection (actual vs estimated return)
- Fuel consumption prediction from BoatFuelLog history
- Night navigation risk
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.boat import Boat
from app.models.location import LocationPing
from app.models.trip import Trip
from app.models.phase5 import BoatFuelLog
from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, TripRiskReport,
)
from app.services.weather_service import get_weather_provider
from app.services.geo import haversine_km


class TripIntelligenceService:
    """Trip intelligence — queries real trip, location, fuel, and weather data."""

    @staticmethod
    def evaluate(db: Session, trip: Trip) -> TripRiskReport:
        """Full trip risk intelligence report."""
        now = datetime.now(timezone.utc)

        overall_risk = TripIntelligenceService._evaluate_overall(db, trip, now)
        delay = TripIntelligenceService._evaluate_delay(trip, now)
        fuel = TripIntelligenceService._evaluate_fuel(db, trip)

        # Weather risk at current position (if we have location)
        weather_decision = None
        latest_ping = (
            db.query(LocationPing)
            .filter(LocationPing.user_id == trip.user_id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )
        if latest_ping:
            weather_decision = TripIntelligenceService._evaluate_trip_weather(
                latest_ping.latitude, latest_ping.longitude,
            )

        # Composite risk score
        risk_values = {"green": 10, "yellow": 40, "red": 70, "critical": 95}
        scores = [risk_values.get(overall_risk.risk_level, 50)]
        scores.append(risk_values.get(delay.risk_level, 10))
        scores.append(risk_values.get(fuel.risk_level, 10))
        if weather_decision:
            scores.append(risk_values.get(weather_decision.risk_level, 10))
        risk_score = max(0, min(100, int(sum(scores) / len(scores))))

        # Fisherman name
        fisherman_name = "Unknown"
        if trip.user:
            fisherman_name = trip.user.full_name or trip.user.phone_number or str(trip.user_id)

        return TripRiskReport(
            trip_id=trip.id,
            fisherman_name=fisherman_name,
            overall_risk=overall_risk,
            delay_assessment=delay,
            fuel_assessment=fuel,
            weather_risk=weather_decision,
            risk_score=risk_score,
        )

    @staticmethod
    def _evaluate_overall(db: Session, trip: Trip, now: datetime) -> DecisionSupport:
        """Overall trip risk from duration, status, time of day."""
        evidence: List[DecisionEvidence] = []
        rules: List[str] = []
        risk_level = "green"

        evidence.append(DecisionEvidence(metric_name="Trip Status", value=trip.status, severity="ok" if trip.status == "active" else "warning"))

        if trip.status == "emergency":
            rules.append("Trip is flagged as EMERGENCY.")
            risk_level = "critical"

        # Duration analysis
        if trip.start_time:
            start_aware = trip.start_time if trip.start_time.tzinfo else trip.start_time.replace(tzinfo=timezone.utc)
            duration_hours = (now - start_aware).total_seconds() / 3600
            evidence.append(DecisionEvidence(metric_name="Trip Duration", value=round(duration_hours, 1), unit="hours", severity="ok" if duration_hours < 12 else "warning"))

            if duration_hours > 24:
                rules.append(f"Trip has been active for {duration_hours:.0f} hours — extended duration risk.")
                risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)
            elif duration_hours > 12:
                rules.append(f"Trip duration ({duration_hours:.0f}h) exceeds typical day trip.")
                risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

            # Night navigation (18:00 to 06:00 local — approximation)
            current_hour = now.hour
            if current_hour >= 18 or current_hour < 6:
                if trip.status == "active":
                    rules.append("Night navigation detected — reduced visibility risk.")
                    risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)
                    evidence.append(DecisionEvidence(metric_name="Night Navigation", value=True, severity="warning"))

        # Distance from start
        if trip.start_latitude and trip.start_longitude:
            latest_ping = (
                db.query(LocationPing)
                .filter(LocationPing.user_id == trip.user_id)
                .order_by(LocationPing.recorded_at.desc())
                .first()
            )
            if latest_ping:
                dist = haversine_km(trip.start_latitude, trip.start_longitude, latest_ping.latitude, latest_ping.longitude)
                evidence.append(DecisionEvidence(metric_name="Distance from Start", value=round(dist, 1), unit="km", severity="ok" if dist < 50 else "warning"))
                if dist > 100:
                    rules.append(f"Vessel is {dist:.0f}km from departure — very far offshore.")
                    risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)
                elif dist > 50:
                    rules.append(f"Vessel is {dist:.0f}km from departure — significant distance.")
                    risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("Trip is within normal operational parameters.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Trip is proceeding normally." if risk_level == "green" else "Trip has elevated risk factors.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.85,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Monitor closely. Contact fisherman if possible.",
        )

    @staticmethod
    def _evaluate_delay(trip: Trip, now: datetime) -> DecisionSupport:
        """Delay detection: compare current time against estimated return."""
        if not trip.estimated_return_at:
            return DecisionSupport(
                recommendation="No estimated return time set — cannot assess delay.",
                reason="Trip was started without an estimated return time.",
                evidence=[DecisionEvidence(metric_name="Estimated Return", value="Not set", severity="warning")],
                confidence_score=0.3,
                priority="normal",
                risk_level="yellow",
                suggested_action="Encourage setting estimated return time for future trips.",
            )

        est_return = trip.estimated_return_at if trip.estimated_return_at.tzinfo else trip.estimated_return_at.replace(tzinfo=timezone.utc)
        delay_minutes = (now - est_return).total_seconds() / 60

        evidence = [
            DecisionEvidence(metric_name="Estimated Return", value=est_return.isoformat(), severity="ok"),
            DecisionEvidence(metric_name="Delay", value=round(delay_minutes, 0), unit="minutes", severity="ok" if delay_minutes < 0 else "warning"),
        ]

        if delay_minutes > 120:
            return DecisionSupport(
                recommendation=f"ALERT: Trip is {delay_minutes:.0f} minutes overdue.",
                reason=f"Expected return was {est_return.strftime('%H:%M')}. Significantly overdue.",
                evidence=evidence,
                confidence_score=0.95,
                priority="critical",
                risk_level="critical",
                suggested_action="Attempt contact immediately. Consider initiating search protocol.",
            )
        elif delay_minutes > 30:
            return DecisionSupport(
                recommendation=f"Trip is {delay_minutes:.0f} minutes past estimated return.",
                reason=f"Expected return was {est_return.strftime('%H:%M')}. Moderately delayed.",
                evidence=evidence,
                confidence_score=0.9,
                priority="high",
                risk_level="red",
                suggested_action="Attempt contact with fisherman.",
            )
        elif delay_minutes > 0:
            return DecisionSupport(
                recommendation=f"Trip is slightly delayed ({delay_minutes:.0f} min past ETA).",
                reason="Minor delay — may be due to conditions or late departure.",
                evidence=evidence,
                confidence_score=0.8,
                priority="normal",
                risk_level="yellow",
                suggested_action="Monitor — escalate if delay exceeds 30 minutes.",
            )
        else:
            return DecisionSupport(
                recommendation="Trip is on schedule.",
                reason=f"Expected return at {est_return.strftime('%H:%M')}. {abs(delay_minutes):.0f} minutes remaining.",
                evidence=evidence,
                confidence_score=0.9,
                priority="low",
                risk_level="green",
            )

    @staticmethod
    def _evaluate_fuel(db: Session, trip: Trip) -> DecisionSupport:
        """Fuel consumption prediction from historical logs."""
        if not trip.boat_id:
            return DecisionSupport(
                recommendation="No boat linked to this trip — cannot assess fuel.",
                reason="Trip does not have a boat_id.",
                evidence=[],
                confidence_score=0.1,
                priority="normal",
                risk_level="yellow",
            )

        fuel_logs = (
            db.query(BoatFuelLog)
            .filter(BoatFuelLog.boat_id == trip.boat_id)
            .order_by(BoatFuelLog.timestamp.desc())
            .limit(20)
            .all()
        )

        if not fuel_logs:
            return DecisionSupport(
                recommendation="No fuel history available for this boat.",
                reason="No fuel logs recorded. Cannot predict consumption.",
                evidence=[DecisionEvidence(metric_name="Fuel Log Count", value=0, severity="warning")],
                confidence_score=0.2,
                priority="normal",
                risk_level="yellow",
                suggested_action="Start recording fuel levels for predictive analysis.",
            )

        # Calculate average consumption
        consumptions = [fl.fuel_consumed_liters for fl in fuel_logs if fl.fuel_consumed_liters and fl.fuel_consumed_liters > 0]
        efficiencies = [fl.efficiency_km_per_liter for fl in fuel_logs if fl.efficiency_km_per_liter and fl.efficiency_km_per_liter > 0]

        evidence = [DecisionEvidence(metric_name="Historical Fuel Logs", value=len(fuel_logs), severity="ok")]

        if consumptions:
            avg_consumption = sum(consumptions) / len(consumptions)
            evidence.append(DecisionEvidence(
                metric_name="Avg Fuel Consumption per Trip", value=round(avg_consumption, 1),
                unit="liters", severity="ok",
            ))

        if efficiencies:
            avg_eff = sum(efficiencies) / len(efficiencies)
            evidence.append(DecisionEvidence(
                metric_name="Avg Fuel Efficiency", value=round(avg_eff, 2),
                unit="km/L", severity="ok" if avg_eff > 2.0 else "warning",
            ))

            # Check boat fuel capacity
            boat = db.query(Boat).filter(Boat.id == trip.boat_id).first()
            if boat and boat.fuel_capacity_liters and avg_eff > 0:
                max_range_km = boat.fuel_capacity_liters * avg_eff
                evidence.append(DecisionEvidence(
                    metric_name="Estimated Max Range", value=round(max_range_km, 0),
                    unit="km", severity="ok",
                ))

        return DecisionSupport(
            recommendation="Fuel data available for trip planning.",
            reason=f"Based on {len(fuel_logs)} historical fuel records.",
            evidence=evidence,
            confidence_score=0.7 if len(fuel_logs) >= 5 else 0.4,
            priority="low",
            risk_level="green",
        )

    @staticmethod
    def _evaluate_trip_weather(lat: float, lon: float) -> DecisionSupport:
        """Quick weather risk check at trip's current position."""
        try:
            obs = get_weather_provider().fetch(lat, lon)
        except Exception:
            return DecisionSupport(
                recommendation="Weather data unavailable at trip location.",
                reason="Weather service returned an error.",
                evidence=[],
                confidence_score=0.1,
                priority="normal",
                risk_level="yellow",
            )

        if not obs.available:
            return DecisionSupport(
                recommendation="Weather data unavailable.",
                reason=obs.unavailable_reason or "No data returned.",
                evidence=[],
                confidence_score=0.1,
                priority="normal",
                risk_level="yellow",
            )

        rules = []
        risk_level = "green"
        evidence = []

        if obs.wind_speed_kmh is not None:
            evidence.append(DecisionEvidence(metric_name="Wind Speed", value=obs.wind_speed_kmh, threshold=40, unit="km/h", severity="ok" if obs.wind_speed_kmh < 25 else ("warning" if obs.wind_speed_kmh < 40 else "danger")))
            if obs.wind_speed_kmh > 60:
                rules.append(f"Storm-force winds ({obs.wind_speed_kmh} km/h).")
                risk_level = "critical"
            elif obs.wind_speed_kmh > 40:
                rules.append(f"High winds ({obs.wind_speed_kmh} km/h).")
                risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)
            elif obs.wind_speed_kmh > 25:
                rules.append(f"Moderate winds ({obs.wind_speed_kmh} km/h).")
                risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if obs.wave_height_m is not None:
            evidence.append(DecisionEvidence(metric_name="Wave Height", value=obs.wave_height_m, threshold=2.5, unit="m", severity="ok" if obs.wave_height_m < 1.5 else ("warning" if obs.wave_height_m < 2.5 else "danger")))
            if obs.wave_height_m > 4.0:
                rules.append(f"Dangerous seas ({obs.wave_height_m}m waves).")
                risk_level = "critical"
            elif obs.wave_height_m > 2.5:
                rules.append(f"Rough seas ({obs.wave_height_m}m waves).")
                risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if not rules:
            rules.append("Weather conditions are acceptable at trip location.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="Weather is favorable." if risk_level == "green" else "Adverse weather at trip location.",
            reason="; ".join(rules),
            evidence=evidence,
            confidence_score=0.85,
            priority=priority_map[risk_level],
            risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Consider return to harbor if conditions worsen.",
        )
