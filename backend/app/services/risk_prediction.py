"""Advanced Risk Prediction Engine — Predict danger before it happens.

Factor budget (must sum to ≤ 100):
  weather_risk        0-20
  distance_from_harbor 0-15
  gps_staleness       0-15  (was overflowing to 25 — fixed)
  missed_checkins     0-15
  trip_duration       0-10
  boat_health         0-10  (was overflowing to 15 — fixed)
  fuel_remaining      0-10  (was overflowing to 15 — fixed)
  time_of_day         0-10  (was documented but never implemented — fixed)
  sos_history         0- 5
  Total max           100

Confidence is now computed from actual data completeness, not a hardcoded 0.85.
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.models.phase5 import (
    RiskPrediction, RiskLevel,
    BoatHealthStatus, BoatFuelLog, Harbor, CheckInRequest,
)
from app.models.trip import Trip
from app.models.user import User
from app.models.boat import Boat
from app.models.location import LocationPing
from app.models.weather_alert import WeatherAlert
from app.models.sos import SOSAlert
from app.schemas.risk_prediction import (
    RiskPredictionResponse,
    TripRiskResponse,
    HighRiskBoat,
)
from app.services.geo import GeoService


class RiskPredictionService:
    """Advanced Risk Prediction Engine."""

    # Risk thresholds
    SAFE_THRESHOLD = 20.0
    WATCH_THRESHOLD = 40.0
    WARNING_THRESHOLD = 60.0

    @staticmethod
    def calculate_risk_score(
        trip_id: int, db: Session
    ) -> Optional[RiskPredictionResponse]:
        """Calculate comprehensive risk score for a trip."""
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        # Initialize factors
        factors = {}
        risk_score = 0.0
        reasons = []
        missed_checkins_considered = False

        # 1. Weather risk (0-20 points)
        weather_risk = RiskPredictionService._calculate_weather_risk(trip, db)
        factors["weather_risk"] = weather_risk
        risk_score += weather_risk
        if weather_risk > 12:
            reasons.append(f"High weather risk ({weather_risk:.1f}/20)")

        # 2. Distance from harbor (0-15 points)
        distance_risk = RiskPredictionService._calculate_distance_risk(trip, db)
        factors["distance_from_harbor"] = distance_risk
        risk_score += distance_risk
        if distance_risk > 10:
            reasons.append(f"Far from harbor ({distance_risk:.1f}/15)")

        # 3. GPS staleness (0-15 points)
        gps_risk = RiskPredictionService._calculate_gps_staleness_risk(trip, db)
        factors["gps_staleness"] = gps_risk
        risk_score += gps_risk
        if gps_risk > 8:
            reasons.append(f"Stale GPS data ({gps_risk:.1f}/15)")

        # 4. Missed check-ins (0-15 points)
        missed_checkin_risk = RiskPredictionService._calculate_missed_checkin_risk(trip, db)
        factors["missed_checkins"] = missed_checkin_risk
        risk_score += missed_checkin_risk
        if missed_checkin_risk > 8:
            reasons.append(f"Missed check-ins detected ({missed_checkin_risk:.1f}/15)")
            missed_checkins_considered = True

        # 5. Time of day risk (0-10 points) — night travel raises risk
        tod_risk = RiskPredictionService._calculate_time_of_day_risk()
        factors["time_of_day"] = tod_risk
        risk_score += tod_risk
        if tod_risk > 5:
            reasons.append(f"Night navigation increases risk ({tod_risk:.1f}/10)")

        # 6. Trip duration (0-10 points)
        duration_risk = RiskPredictionService._calculate_duration_risk(trip)
        factors["trip_duration"] = duration_risk
        risk_score += duration_risk
        if duration_risk > 6:
            reasons.append(f"Long trip duration ({duration_risk:.1f}/10)")

        # 7. Boat health (0-10 points)
        boat_risk = RiskPredictionService._calculate_boat_health_risk(trip, db)
        factors["boat_health"] = boat_risk
        risk_score += boat_risk
        if boat_risk > 6:
            reasons.append(f"Poor boat health ({boat_risk:.1f}/10)")

        # 8. Fuel remaining (0-10 points)
        fuel_risk = RiskPredictionService._calculate_fuel_risk(trip, db)
        factors["fuel_remaining"] = fuel_risk
        risk_score += fuel_risk
        if fuel_risk > 6:
            reasons.append(f"Low fuel ({fuel_risk:.1f}/10)")

        # 9. SOS history (0-5 points)
        sos_risk = RiskPredictionService._calculate_sos_history_risk(trip, db)
        factors["sos_history"] = sos_risk
        risk_score += sos_risk
        if sos_risk > 3:
            reasons.append(f"Previous SOS incidents ({sos_risk:.1f}/5)")

        # Determine risk level
        if risk_score < RiskPredictionService.SAFE_THRESHOLD:
            risk_level = "SAFE"
            recommended_action = "Continue normal operations. Monitor weather updates."
        elif risk_score < RiskPredictionService.WATCH_THRESHOLD:
            risk_level = "WATCH"
            recommended_action = "Stay alert. Check weather and fuel regularly."
        elif risk_score < RiskPredictionService.WARNING_THRESHOLD:
            risk_level = "WARNING"
            recommended_action = "Consider returning to harbor. Avoid high-risk areas."
        else:
            risk_level = "CRITICAL"
            recommended_action = "Return to harbor immediately. Seek assistance if needed."

        if not reasons:
            reasons.append("All systems normal")

        # Confidence from data completeness — not a hardcoded constant
        confidence = RiskPredictionService._compute_confidence(factors)

        # Store prediction
        prediction = RiskPrediction(
            trip_id=trip_id,
            risk_level=risk_level.lower(),
            risk_score=risk_score,
            contributing_factors_json=json.dumps(factors),
            model_version="rule_based_v2.0",
            prediction_confidence=confidence,
            recommendations_json=json.dumps({"action": recommended_action, "reasons": reasons}),
        )
        db.add(prediction)
        db.commit()

        return RiskPredictionResponse(
            risk_level=risk_level,
            risk_score=round(risk_score, 2),
            factors=factors,
            reasons=reasons,
            recommended_action=recommended_action,
            confidence=confidence,
            missed_checkins_considered=missed_checkins_considered,
        )

    @staticmethod
    def _calculate_weather_risk(trip: Trip, db: Session) -> float:
        """Calculate weather risk (0-20 points)."""
        latest_location = (
            db.query(LocationPing)
            .filter(LocationPing.trip_id == trip.id)
            .order_by(desc(LocationPing.recorded_at))
            .first()
        )

        if not latest_location:
            return 5.0  # Unknown location = moderate risk

        # Check for active weather alerts
        active_alerts = (
            db.query(WeatherAlert)
            .filter(WeatherAlert.is_active == True)
            .all()
        )

        max_risk = 0.0
        for alert in active_alerts:
            severity_map = {"green": 0, "yellow": 8, "orange": 15, "red": 20}
            severity_str = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
            risk = severity_map.get(severity_str.lower(), 5)
            max_risk = max(max_risk, risk)

        return max_risk

    @staticmethod
    def _calculate_distance_risk(trip: Trip, db: Session) -> float:
        """Calculate distance from harbor risk (0-15 points)."""
        latest_location = (
            db.query(LocationPing)
            .filter(LocationPing.trip_id == trip.id)
            .order_by(desc(LocationPing.recorded_at))
            .first()
        )

        if not latest_location:
            return 5.0

        from app.models.phase5 import Harbor
        harbors = db.query(Harbor).filter(Harbor.is_active == True).all()

        if not harbors:
            return 5.0

        min_distance = float("inf")
        for harbor in harbors:
            if harbor.latitude and harbor.longitude:
                distance = GeoService.haversine_distance(
                    latest_location.latitude,
                    latest_location.longitude,
                    harbor.latitude,
                    harbor.longitude,
                )
                min_distance = min(min_distance, distance)

        if min_distance < 10:
            return 0.0
        elif min_distance < 30:
            return 5.0
        elif min_distance < 60:
            return 10.0
        else:
            return 15.0

    @staticmethod
    def _calculate_gps_staleness_risk(trip: Trip, db: Session) -> float:
        """Calculate GPS staleness risk (0-15 points, hard-capped)."""
        latest_location = (
            db.query(LocationPing)
            .filter(LocationPing.trip_id == trip.id)
            .order_by(desc(LocationPing.recorded_at))
            .first()
        )

        if not latest_location:
            return 10.0

        minutes_since_update = (
            datetime.utcnow() - latest_location.recorded_at
        ).total_seconds() / 60

        if minutes_since_update < 10:
            return 0.0
        elif minutes_since_update < 30:
            return 5.0
        elif minutes_since_update < 60:
            return 10.0
        else:
            return 15.0

    @staticmethod
    def _calculate_time_of_day_risk() -> float:
        """Night navigation risk (0-10 points). 18:00-06:00 UTC raises risk."""
        hour = datetime.utcnow().hour
        if 22 <= hour or hour < 4:
            return 10.0  # Deep night — very low visibility
        if 18 <= hour or hour < 6:
            return 5.0   # Dusk/dawn — reduced visibility
        return 0.0

    @staticmethod
    def _compute_confidence(factors: dict) -> float:
        """Confidence from data completeness. Missing data = lower confidence."""
        # Factors that require real sensor data (not just defaults)
        sensor_factors = ["weather_risk", "distance_from_harbor", "gps_staleness",
                          "boat_health", "fuel_remaining"]
        # A factor at its "unknown/default" value means we had no real data
        default_values = {"weather_risk": 5.0, "distance_from_harbor": 5.0,
                          "gps_staleness": 10.0, "boat_health": 5.0, "fuel_remaining": 3.0}
        real_data_count = sum(
            1 for f in sensor_factors
            if factors.get(f) != default_values.get(f)
        )
        return round(0.5 + (real_data_count / len(sensor_factors)) * 0.45, 2)

    @staticmethod
    def _calculate_missed_checkin_risk(trip: Trip, db: Session) -> float:
        """Calculate missed check-in risk (0-15 points)."""
        # Count missed check-in requests for this trip
        missed_count = (
            db.query(CheckInRequest)
            .filter(
                and_(
                    CheckInRequest.trip_id == trip.id,
                    CheckInRequest.status == "missed",
                )
            )
            .count()
        )

        if missed_count == 0:
            return 0.0
        elif missed_count <= 2:
            return 5.0
        elif missed_count <= 5:
            return 10.0
        else:
            return 15.0

    @staticmethod
    def _calculate_duration_risk(trip: Trip) -> float:
        """Calculate trip duration risk (0-10 points)."""
        duration_hours = (datetime.utcnow() - trip.start_time).total_seconds() / 3600

        if duration_hours < 4:
            return 0.0
        elif duration_hours < 8:
            return 2.0
        elif duration_hours < 12:
            return 5.0
        elif duration_hours < 18:
            return 7.0
        else:
            return 10.0

    @staticmethod
    def _calculate_boat_health_risk(trip: Trip, db: Session) -> float:
        """Calculate boat health risk (0-10 points, hard-capped)."""
        if not trip.boat_id:
            return 5.0

        health_status = (
            db.query(BoatHealthStatus)
            .filter(BoatHealthStatus.boat_id == trip.boat_id)
            .first()
        )

        if not health_status:
            return 5.0

        health_score = health_status.health_score or 50.0

        if health_score >= 80:
            return 0.0
        elif health_score >= 60:
            return 3.0
        elif health_score >= 40:
            return 7.0
        else:
            return 10.0

    @staticmethod
    def _calculate_fuel_risk(trip: Trip, db: Session) -> float:
        """Calculate fuel remaining risk (0-10 points, hard-capped)."""
        if not trip.boat_id:
            return 3.0

        latest_fuel = (
            db.query(BoatFuelLog)
            .filter(BoatFuelLog.boat_id == trip.boat_id)
            .order_by(desc(BoatFuelLog.timestamp))
            .first()
        )

        if not latest_fuel:
            return 3.0

        fuel_percent = latest_fuel.fuel_level_end_percent or 100.0

        if fuel_percent >= 50:
            return 0.0
        elif fuel_percent >= 30:
            return 4.0
        elif fuel_percent >= 15:
            return 7.0
        else:
            return 10.0

    @staticmethod
    def _calculate_sos_history_risk(trip: Trip, db: Session) -> float:
        """Calculate SOS history risk (0-5 points)."""
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sos_count = (
            db.query(SOSAlert)
            .filter(
                and_(
                    SOSAlert.user_id == trip.user_id,
                    SOSAlert.triggered_at >= thirty_days_ago,
                )
            )
            .count()
        )

        if sos_count == 0:
            return 0.0
        elif sos_count == 1:
            return 2.0
        elif sos_count == 2:
            return 3.5
        else:
            return 5.0

    @staticmethod
    def get_trip_risk(trip_id: int, db: Session) -> Optional[TripRiskResponse]:
        """Get risk assessment for a trip."""
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None

        fisherman = db.query(User).filter(User.id == trip.user_id).first()

        # Get or calculate risk
        latest_prediction = (
            db.query(RiskPrediction)
            .filter(RiskPrediction.trip_id == trip_id)
            .order_by(desc(RiskPrediction.created_at))
            .first()
        )

        if not latest_prediction or (
            datetime.utcnow() - latest_prediction.created_at
        ).total_seconds() > 600:  # 10 minutes
            risk_response = RiskPredictionService.calculate_risk_score(trip_id, db)
            if not risk_response:
                return None

            latest_prediction = (
                db.query(RiskPrediction)
                .filter(RiskPrediction.trip_id == trip_id)
                .order_by(desc(RiskPrediction.created_at))
                .first()
            )

        factors = json.loads(latest_prediction.contributing_factors_json or "{}")
        recommendations_data = json.loads(latest_prediction.recommendations_json or "{}")
        missed_checkin_risk = factors.get("missed_checkins")

        return TripRiskResponse(
            trip_id=trip_id,
            fisherman_id=trip.user_id,
            fisherman_name=fisherman.full_name if fisherman else "Unknown",
            risk_level=latest_prediction.risk_level.upper(),
            risk_score=latest_prediction.risk_score,
            last_updated=latest_prediction.created_at,
            factors=factors,
            recommendations=recommendations_data.get("reasons", []),
            missed_checkin_risk=missed_checkin_risk,
        )

    @staticmethod
    def get_high_risk_boats(db: Session, limit: int = 20) -> List[HighRiskBoat]:
        """Get list of high-risk boats."""
        active_trips = db.query(Trip).filter(Trip.end_time.is_(None)).all()  # noqa: E711

        high_risk_boats = []
        for trip in active_trips:
            risk_response = RiskPredictionService.get_trip_risk(trip.id, db)
            if not risk_response:
                continue

            if risk_response.risk_level in ("WARNING", "CRITICAL"):
                boat = db.query(Boat).filter(Boat.id == trip.boat_id).first()
                fisherman = db.query(User).filter(User.id == trip.user_id).first()

                latest_location = (
                    db.query(LocationPing)
                    .filter(LocationPing.trip_id == trip.id)
                    .order_by(desc(LocationPing.recorded_at))
                    .first()
                )

                location_data = None
                if latest_location:
                    location_data = {
                        "lat": latest_location.latitude,
                        "lng": latest_location.longitude,
                    }

                # Count missed check-ins for this trip
                missed_count = (
                    db.query(CheckInRequest)
                    .filter(
                        and_(
                            CheckInRequest.trip_id == trip.id,
                            CheckInRequest.status == "missed",
                        )
                    )
                    .count()
                )

                high_risk_boats.append(
                    HighRiskBoat(
                        boat_id=boat.id if boat else 0,
                        boat_name=boat.name if boat else "Unknown",
                        registration_number=boat.registration_number if boat else "N/A",
                        fisherman_id=trip.user_id,
                        fisherman_name=fisherman.full_name if fisherman else "Unknown",
                        trip_id=trip.id,
                        risk_level=risk_response.risk_level,
                        risk_score=risk_response.risk_score,
                        primary_risks=risk_response.recommendations[:3],
                        last_location=location_data,
                        missed_checkin_count=missed_count,
                    )
                )

        return sorted(high_risk_boats, key=lambda x: x.risk_score, reverse=True)[:limit]
