"""
Weather Intelligence (docs/WEATHER_INTELLIGENCE.md) — V2 core build Phase 10.

V1 had a `WEATHER_PROVIDER=open-meteo` setting that nothing ever read
(docs/V1_AUDIT.md §6/§9) — all weather data came from a manually-seeded
static table. This is the real integration: Open-Meteo's forecast + marine
APIs are free and require no API key, so the default provider is genuinely
live, not simulated.

Provider abstraction so no business logic is coupled to one vendor:
  WeatherProvider (interface)
    -> OpenMeteoProvider   (real HTTP calls, default)
    -> SimulatedProvider   (deterministic synthetic data, explicitly
                             labeled, used only if WEATHER_PROVIDER is set
                             to "simulated" — e.g. offline dev/demo)

On a real-provider failure (network error, timeout, non-200), the caller
gets `available=False` and an explanation — never fabricated numbers
standing in for a failed live call.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings


@dataclass
class WeatherObservation:
    latitude: float
    longitude: float
    source: str  # "open-meteo" | "SIMULATED"
    timestamp: str
    available: bool
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    wave_height_m: float | None = None
    wave_direction_deg: float | None = None
    precipitation_mm: float | None = None
    pressure_hpa: float | None = None
    visibility_m: float | None = None
    unavailable_reason: str | None = None


class WeatherProvider(ABC):
    @abstractmethod
    def fetch(self, latitude: float, longitude: float) -> WeatherObservation: ...


class OpenMeteoProvider(WeatherProvider):
    """Real, keyless marine + atmospheric data from open-meteo.com. Two
    endpoints because wave data (marine-api) and wind/rain/pressure
    (api.open-meteo.com) are separate Open-Meteo products; both are
    optional-if-unavailable rather than all-or-nothing, since marine data
    only covers ocean coordinates."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

    def fetch(self, latitude: float, longitude: float) -> WeatherObservation:
        import httpx

        now = datetime.now(timezone.utc)
        wind_speed = wind_dir = precip = pressure = visibility = None
        wave_height = wave_dir = None
        errors: list[str] = []

        try:
            with httpx.Client(timeout=settings.weather_http_timeout_seconds) as client:
                resp = client.get(
                    self.FORECAST_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "wind_speed_10m,wind_direction_10m,precipitation,surface_pressure,visibility",
                        "timezone": "UTC",
                    },
                )
                resp.raise_for_status()
                current = resp.json().get("current", {})
                wind_speed = current.get("wind_speed_10m")
                wind_dir = current.get("wind_direction_10m")
                precip = current.get("precipitation")
                pressure = current.get("surface_pressure")
                visibility = current.get("visibility")
        except Exception as e:
            errors.append(f"forecast: {e}")

        try:
            with httpx.Client(timeout=settings.weather_http_timeout_seconds) as client:
                resp = client.get(
                    self.MARINE_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "wave_height,wave_direction",
                        "timezone": "UTC",
                    },
                )
                resp.raise_for_status()
                current = resp.json().get("current", {})
                wave_height = current.get("wave_height")
                wave_dir = current.get("wave_direction")
        except Exception as e:
            errors.append(f"marine: {e}")

        # Available if at least one of the two calls produced real data —
        # a boat far from any marine-data coverage but with valid
        # atmospheric data is still useful information.
        got_anything = any(v is not None for v in (wind_speed, precip, pressure, visibility, wave_height))
        return WeatherObservation(
            latitude=latitude,
            longitude=longitude,
            source="open-meteo",
            timestamp=now.isoformat(),
            available=got_anything,
            wind_speed_kmh=wind_speed,
            wind_direction_deg=wind_dir,
            wave_height_m=wave_height,
            wave_direction_deg=wave_dir,
            precipitation_mm=precip,
            pressure_hpa=pressure,
            visibility_m=visibility,
            unavailable_reason=None if got_anything else "; ".join(errors) or "No data returned",
        )


class SimulatedProvider(WeatherProvider):
    """Deterministic, clearly-labeled synthetic data — never returned
    unless WEATHER_PROVIDER=simulated is explicitly configured. Values are
    a fixed function of the coordinates (not random) so results are
    reproducible for demos/tests."""

    def fetch(self, latitude: float, longitude: float) -> WeatherObservation:
        now = datetime.now(timezone.utc)
        seed = abs(int((latitude * 1000 + longitude * 1000)) % 40)
        return WeatherObservation(
            latitude=latitude,
            longitude=longitude,
            source="SIMULATED",
            timestamp=now.isoformat(),
            available=True,
            wind_speed_kmh=10.0 + seed,
            wind_direction_deg=float((seed * 9) % 360),
            wave_height_m=round(0.5 + seed / 20, 2),
            wave_direction_deg=float((seed * 7) % 360),
            precipitation_mm=round(seed / 40, 2),
            pressure_hpa=1008.0 - seed / 4,
            visibility_m=10000.0 - seed * 100,
        )


def get_weather_provider() -> WeatherProvider:
    if settings.weather_provider == "simulated":
        return SimulatedProvider()
    return OpenMeteoProvider()
