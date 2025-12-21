"""Geographic calculations - Pure functions.

This module provides distance and boundary calculations for earthquake locations.
All functions are pure with no side effects.
"""

import math
from dataclasses import dataclass

from src.core.earthquake import Earthquake


# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounding box.

    Attributes:
        min_latitude: Southern boundary
        max_latitude: Northern boundary
        min_longitude: Western boundary
        max_longitude: Eastern boundary
    """
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float

    def contains(self, latitude: float, longitude: float) -> bool:
        """Check if a point is within this bounding box."""
        return (
            self.min_latitude <= latitude <= self.max_latitude
            and self.min_longitude <= longitude <= self.max_longitude
        )


@dataclass(frozen=True)
class PointOfInterest:
    """A named location for proximity alerts.

    Attributes:
        name: Human-readable name (e.g., "Office", "Home")
        latitude: Location latitude
        longitude: Location longitude
        alert_radius_km: Alert when earthquake is within this radius
    """
    name: str
    latitude: float
    longitude: float
    alert_radius_km: float


def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate distance between two points using Haversine formula.

    Pure function.

    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point

    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def is_within_bounds(earthquake: Earthquake, bounds: BoundingBox) -> bool:
    """Check if an earthquake is within a bounding box.

    Pure function.

    Args:
        earthquake: Earthquake to check
        bounds: Bounding box to check against

    Returns:
        True if earthquake is within bounds
    """
    return bounds.contains(earthquake.latitude, earthquake.longitude)


def is_within_radius(
    earthquake: Earthquake,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> bool:
    """Check if an earthquake is within a radius of a point.

    Pure function.

    Args:
        earthquake: Earthquake to check
        center_lat: Center point latitude
        center_lon: Center point longitude
        radius_km: Radius in kilometers

    Returns:
        True if earthquake is within radius
    """
    distance = calculate_distance(
        earthquake.latitude,
        earthquake.longitude,
        center_lat,
        center_lon,
    )
    return distance <= radius_km


def get_distance_to_poi(earthquake: Earthquake, poi: PointOfInterest) -> float:
    """Calculate distance from earthquake to a point of interest.

    Pure function.

    Args:
        earthquake: The earthquake
        poi: Point of interest

    Returns:
        Distance in kilometers
    """
    return calculate_distance(
        earthquake.latitude,
        earthquake.longitude,
        poi.latitude,
        poi.longitude,
    )


def filter_by_bounds(
    earthquakes: list[Earthquake],
    bounds: BoundingBox,
) -> list[Earthquake]:
    """Filter earthquakes to only those within a bounding box.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        bounds: Bounding box to filter by

    Returns:
        Earthquakes within the bounds
    """
    return [e for e in earthquakes if is_within_bounds(e, bounds)]


def filter_by_proximity(
    earthquakes: list[Earthquake],
    poi: PointOfInterest,
) -> list[Earthquake]:
    """Filter earthquakes to only those within a POI's alert radius.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        poi: Point of interest with alert radius

    Returns:
        Earthquakes within the POI's alert radius
    """
    return [
        e for e in earthquakes
        if is_within_radius(e, poi.latitude, poi.longitude, poi.alert_radius_km)
    ]
