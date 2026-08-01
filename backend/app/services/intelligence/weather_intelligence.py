"""
OceanGuardian AI — Weather Intelligence Service.

Full weather risk assessment using the real weather provider (Open-Meteo):
- Wind Risk (Beaufort scale mapping)
- Wave Risk (sea state classification)
- Visibility Risk
- Storm Risk (combined wind + precipitation)
- Overall Fishing Safety recommendation
- Weather Confidence Score
"""
from typing import List

from app.schemas.intelligence import (
    DecisionEvidence, DecisionSupport, WeatherRiskReport,
)
from app.services.weather_service import get_weather_provider, WeatherObservation


# ── Beaufort Scale thresholds (km/h) ──────────────────────────────
_BEAUFORT = [
    (1, "Calm"),
    (6, "Light Air"),
    (12, "Light Breeze"),
    (20, "Gentle Breeze"),
    (29, "Moderate Breeze"),
    (39, "Fresh Breeze"),
    (50, "Strong Breeze"),
    (62, "Near Gale"),
    (75, "Gale"),
    (89, "Strong Gale"),
    (103, "Storm"),
    (118, "Violent Storm"),
    (999, "Hurricane Force"),
]

# ── Sea State (WMO) by wave height (m) ───────────────────────────
_SEA_STATE = [
    (0.0, "Calm (Glassy)"),
    (0.1, "Calm (Rippled)"),
    (0.5, "Smooth"),
    (1.25, "Slight"),
    (2.5, "Moderate"),
    (4.0, "Rough"),
    (6.0, "Very Rough"),
    (9.0, "High"),
    (14.0, "Very High"),
    (999, "Phenomenal"),
]


def _beaufort(speed_kmh: float) -> str:
    for threshold, name in _BEAUFORT:
        if speed_kmh <= threshold:
            return name
    return "Hurricane Force"


def _sea_state(height_m: float) -> str:
    for threshold, name in _SEA_STATE:
        if height_m <= threshold:
            return name
    return "Phenomenal"


class WeatherIntelligenceService:
    """Weather intelligence — queries real weather provider."""

    @staticmethod
    def evaluate(latitude: float, longitude: float) -> WeatherRiskReport:
        """Full weather risk report for a location."""
        try:
            obs = get_weather_provider().fetch(latitude, longitude)
        except Exception as e:
            # Total failure — return degraded report
            unavailable = DecisionSupport(
                recommendation="Weather data unavailable.",
                reason=str(e),
                evidence=[],
                confidence_score=0.0,
                priority="normal",
                risk_level="yellow",
            )
            return WeatherRiskReport(
                latitude=latitude, longitude=longitude,
                wind_risk=unavailable, wave_risk=unavailable,
                visibility_risk=unavailable, storm_risk=unavailable,
                overall_fishing_safety=unavailable, weather_confidence=0.0,
            )

        wind = WeatherIntelligenceService._assess_wind(obs)
        wave = WeatherIntelligenceService._assess_wave(obs)
        visibility = WeatherIntelligenceService._assess_visibility(obs)
        storm = WeatherIntelligenceService._assess_storm(obs)
        overall = WeatherIntelligenceService._assess_overall(obs, wind, wave, visibility, storm)

        # Confidence: 1.0 if all data present, reduced for each missing field
        data_fields = [obs.wind_speed_kmh, obs.wave_height_m, obs.visibility_m, obs.precipitation_mm, obs.pressure_hpa]
        present = sum(1 for f in data_fields if f is not None)
        confidence = round(present / len(data_fields), 2) if obs.available else 0.0

        return WeatherRiskReport(
            latitude=latitude, longitude=longitude,
            wind_risk=wind, wave_risk=wave,
            visibility_risk=visibility, storm_risk=storm,
            overall_fishing_safety=overall,
            weather_confidence=confidence,
        )

    @staticmethod
    def _assess_wind(obs: WeatherObservation) -> DecisionSupport:
        if obs.wind_speed_kmh is None:
            return DecisionSupport(
                recommendation="Wind data unavailable.",
                reason="Weather provider did not return wind speed.",
                evidence=[], confidence_score=0.0,
                priority="normal", risk_level="yellow",
            )

        speed = obs.wind_speed_kmh
        beaufort = _beaufort(speed)
        evidence = [
            DecisionEvidence(metric_name="Wind Speed", value=speed, unit="km/h", threshold=40, severity="ok" if speed < 25 else ("warning" if speed < 50 else "danger")),
            DecisionEvidence(metric_name="Beaufort Scale", value=beaufort, severity="ok" if speed < 40 else "danger"),
        ]
        if obs.wind_direction_deg is not None:
            evidence.append(DecisionEvidence(metric_name="Wind Direction", value=obs.wind_direction_deg, unit="°", severity="ok"))

        if speed > 75:
            return DecisionSupport(recommendation="DANGER: Gale/storm force winds — do NOT venture out.", reason=f"Wind at {speed} km/h ({beaufort}). Extremely dangerous for all vessels.", evidence=evidence, confidence_score=0.95, priority="critical", risk_level="critical", suggested_action="Seek shelter immediately. Do not depart.")
        if speed > 50:
            return DecisionSupport(recommendation="Strong winds — fishing not recommended.", reason=f"Wind at {speed} km/h ({beaufort}). Dangerous for small boats.", evidence=evidence, confidence_score=0.9, priority="high", risk_level="red", suggested_action="Return to harbor if at sea.")
        if speed > 25:
            return DecisionSupport(recommendation="Moderate winds — exercise caution.", reason=f"Wind at {speed} km/h ({beaufort}). Manageable but uncomfortable.", evidence=evidence, confidence_score=0.85, priority="normal", risk_level="yellow", suggested_action="Stay close to shore. Monitor conditions.")
        return DecisionSupport(recommendation="Wind conditions are favorable.", reason=f"Wind at {speed} km/h ({beaufort}).", evidence=evidence, confidence_score=0.9, priority="low", risk_level="green")

    @staticmethod
    def _assess_wave(obs: WeatherObservation) -> DecisionSupport:
        if obs.wave_height_m is None:
            return DecisionSupport(
                recommendation="Wave data unavailable.",
                reason="Marine data not returned (may be inland coordinates).",
                evidence=[], confidence_score=0.0,
                priority="normal", risk_level="yellow",
            )

        height = obs.wave_height_m
        sea = _sea_state(height)
        evidence = [
            DecisionEvidence(metric_name="Wave Height", value=height, unit="m", threshold=2.5, severity="ok" if height < 1.25 else ("warning" if height < 4.0 else "danger")),
            DecisionEvidence(metric_name="Sea State (WMO)", value=sea, severity="ok" if height < 2.5 else "danger"),
        ]

        if height > 6.0:
            return DecisionSupport(recommendation="DANGER: Very rough to high seas — fishing impossible.", reason=f"Waves at {height}m ({sea}). Life-threatening for small vessels.", evidence=evidence, confidence_score=0.95, priority="critical", risk_level="critical", suggested_action="Do NOT go to sea. Seek harbor shelter.")
        if height > 2.5:
            return DecisionSupport(recommendation="Rough seas — not suitable for fishing.", reason=f"Waves at {height}m ({sea}).", evidence=evidence, confidence_score=0.9, priority="high", risk_level="red", suggested_action="Return to port if at sea.")
        if height > 1.25:
            return DecisionSupport(recommendation="Moderate swells — small boats should exercise caution.", reason=f"Waves at {height}m ({sea}).", evidence=evidence, confidence_score=0.85, priority="normal", risk_level="yellow", suggested_action="Stay near shore. Wear life jackets.")
        return DecisionSupport(recommendation="Sea conditions are calm and suitable for fishing.", reason=f"Waves at {height}m ({sea}).", evidence=evidence, confidence_score=0.9, priority="low", risk_level="green")

    @staticmethod
    def _assess_visibility(obs: WeatherObservation) -> DecisionSupport:
        if obs.visibility_m is None:
            return DecisionSupport(
                recommendation="Visibility data unavailable.",
                reason="Provider did not return visibility.",
                evidence=[], confidence_score=0.0,
                priority="normal", risk_level="yellow",
            )

        vis = obs.visibility_m
        vis_km = vis / 1000
        evidence = [DecisionEvidence(metric_name="Visibility", value=round(vis_km, 1), unit="km", threshold=5, severity="ok" if vis_km > 5 else ("warning" if vis_km > 1 else "danger"))]

        if vis_km < 0.5:
            return DecisionSupport(recommendation="DANGER: Near-zero visibility — fog or heavy rain.", reason=f"Visibility {vis_km:.1f}km. Collision risk extremely high.", evidence=evidence, confidence_score=0.95, priority="critical", risk_level="critical", suggested_action="Do not navigate. Use foghorn. Anchor if safe.")
        if vis_km < 2:
            return DecisionSupport(recommendation="Poor visibility — navigation hazardous.", reason=f"Visibility {vis_km:.1f}km.", evidence=evidence, confidence_score=0.9, priority="high", risk_level="red", suggested_action="Reduce speed. Use navigation lights.")
        if vis_km < 5:
            return DecisionSupport(recommendation="Reduced visibility — proceed with caution.", reason=f"Visibility {vis_km:.1f}km.", evidence=evidence, confidence_score=0.85, priority="normal", risk_level="yellow", suggested_action="Keep watch for other vessels.")
        return DecisionSupport(recommendation="Good visibility.", reason=f"Visibility {vis_km:.1f}km.", evidence=evidence, confidence_score=0.9, priority="low", risk_level="green")

    @staticmethod
    def _assess_storm(obs: WeatherObservation) -> DecisionSupport:
        """Combined wind + precipitation to detect storm conditions."""
        evidence: List[DecisionEvidence] = []
        risk_level = "green"
        rules = []

        wind = obs.wind_speed_kmh or 0
        rain = obs.precipitation_mm or 0
        pressure = obs.pressure_hpa

        if pressure is not None:
            evidence.append(DecisionEvidence(metric_name="Pressure", value=pressure, unit="hPa", threshold=1000, severity="ok" if pressure > 1005 else ("warning" if pressure > 995 else "danger")))
            if pressure < 990:
                rules.append(f"Very low pressure ({pressure} hPa) — storm system likely.")
                risk_level = "critical"
            elif pressure < 1000:
                rules.append(f"Low pressure ({pressure} hPa) — weather system approaching.")
                risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)

        if rain > 10:
            evidence.append(DecisionEvidence(metric_name="Rainfall", value=rain, unit="mm/h", threshold=5, severity="danger"))
            rules.append(f"Heavy rainfall ({rain} mm/h).")
            risk_level = max(risk_level, "red", key=["green", "yellow", "red", "critical"].index)
        elif rain > 2:
            evidence.append(DecisionEvidence(metric_name="Rainfall", value=rain, unit="mm/h", threshold=5, severity="warning"))
            rules.append(f"Moderate rainfall ({rain} mm/h).")
            risk_level = max(risk_level, "yellow", key=["green", "yellow", "red", "critical"].index)

        if wind > 60 and rain > 5:
            rules.append("Storm conditions: high wind combined with significant rainfall.")
            risk_level = "critical"

        if not rules:
            rules.append("No storm indicators detected.")

        priority_map = {"green": "low", "yellow": "normal", "red": "high", "critical": "critical"}
        return DecisionSupport(
            recommendation="No storm risk." if risk_level == "green" else "Storm conditions detected or approaching.",
            reason="; ".join(rules), evidence=evidence,
            confidence_score=0.8 if pressure is not None else 0.5,
            priority=priority_map[risk_level], risk_level=risk_level,
            suggested_action=None if risk_level == "green" else "Seek harbor shelter. Monitor weather updates.",
        )

    @staticmethod
    def _assess_overall(obs: WeatherObservation, wind: DecisionSupport, wave: DecisionSupport, vis: DecisionSupport, storm: DecisionSupport) -> DecisionSupport:
        """Overall fishing safety — worst-case of sub-assessments."""
        risk_order = ["green", "yellow", "red", "critical"]
        worst = max(
            [wind.risk_level, wave.risk_level, vis.risk_level, storm.risk_level],
            key=lambda r: risk_order.index(r) if r in risk_order else 0,
        )

        if worst == "critical":
            return DecisionSupport(recommendation="DO NOT GO FISHING. Dangerous conditions.", reason="One or more weather parameters are at critical levels.", evidence=[], confidence_score=0.95, priority="critical", risk_level="critical", suggested_action="Stay in port. Wait for conditions to improve.", alternative_recommendations=["Check forecast for tomorrow.", "Move to a sheltered harbor."])
        if worst == "red":
            return DecisionSupport(recommendation="Fishing NOT recommended. Elevated risk.", reason="Significant weather hazards detected.", evidence=[], confidence_score=0.9, priority="high", risk_level="red", suggested_action="If at sea, return to harbor.", alternative_recommendations=["Wait for improvement.", "Try sheltered fishing grounds."])
        if worst == "yellow":
            return DecisionSupport(recommendation="Fishing possible with CAUTION.", reason="Some weather parameters require attention.", evidence=[], confidence_score=0.8, priority="normal", risk_level="yellow", suggested_action="Stay close to shore. Wear life jackets. Monitor updates.")
        return DecisionSupport(recommendation="Conditions are FAVORABLE for fishing.", reason="All weather parameters within safe limits.", evidence=[], confidence_score=0.9, priority="low", risk_level="green")
