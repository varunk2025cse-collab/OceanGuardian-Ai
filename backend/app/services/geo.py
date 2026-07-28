"""Geo helpers: haversine distance and compass bearing."""
from math import radians, sin, cos, sqrt, atan2, degrees


class GeoService:
    """Geographic calculation service (wrapper for backward compatibility)."""

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two lat/lon points, in kilometers."""
        return haversine_km(lat1, lon1, lat2, lon2)

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two lat/lon points, in kilometers."""
        return haversine_km(lat1, lon1, lat2, lon2)

    @staticmethod
    def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Initial compass bearing from point 1 to point 2 (0–360°)."""
        return bearing_degrees(lat1, lon1, lat2, lon2)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2 (0–360°, clockwise from north)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dlambda = radians(lon2 - lon1)
    x = sin(dlambda) * cos(phi2)
    y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlambda)
    bearing = (degrees(atan2(x, y)) + 360) % 360
    return bearing


_COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def compass_direction(bearing: float) -> str:
    """8-point compass label (N/NE/E/SE/S/SW/W/NW) for a bearing in degrees —
    a fisherman reads "head Northeast" far faster under stress than a raw
    degree number. Navigation AI (docs/NAVIGATION_AI.md)."""
    index = round((bearing % 360) / 45) % 8
    return _COMPASS_POINTS[index]
