from sqlalchemy.orm import Session
from app.schemas.intelligence import DecisionSupport
from app.services.intelligence.provider import get_explainable_provider, IntelligenceContext
from app.services.weather_service import get_weather_provider

class WeatherIntelligenceService:
    @staticmethod
    def evaluate_weather_risk(latitude: float, longitude: float) -> DecisionSupport:
        """
        Evaluate weather risk at a specific location.
        """
        weather_provider = get_weather_provider()
        obs = weather_provider.fetch(latitude, longitude)
        
        rules_triggered = []
        risk_level = "green"
        
        data = {
            "wind_speed_kmh": obs.wind_speed_kmh,
            "wave_height_m": obs.wave_height_m,
            "available": obs.available
        }

        if not obs.available:
            rules_triggered.append("Weather data is currently unavailable.")
            risk_level = "yellow"
        else:
            if obs.wind_speed_kmh is not None and obs.wind_speed_kmh > 40:
                rules_triggered.append(f"High wind speed detected: {obs.wind_speed_kmh} km/h.")
                risk_level = "red"
            
            if obs.wave_height_m is not None and obs.wave_height_m > 2.5:
                rules_triggered.append(f"Dangerous wave heights detected: {obs.wave_height_m} m.")
                risk_level = "red"
                
            if risk_level == "red" and obs.wind_speed_kmh is not None and obs.wind_speed_kmh > 60:
                risk_level = "critical"

        context = IntelligenceContext(
            target_name=f"Location ({latitude}, {longitude})",
            context_type="Weather Risk Assessment",
            data={**data, "risk_level": risk_level},
            rules_triggered=rules_triggered
        )
        
        provider = get_explainable_provider()
        return provider.explain(context)
