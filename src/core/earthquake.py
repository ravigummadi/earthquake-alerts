"""Earthquake data models and parsing - Pure functions.

This module handles parsing USGS GeoJSON data into typed Earthquake objects.
All functions are pure with no side effects.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Earthquake:
    """Immutable earthquake data model.

    Attributes:
        id: Unique USGS event ID
        magnitude: Earthquake magnitude (Richter scale)
        place: Human-readable location description
        time: Event timestamp (UTC)
        latitude: Epicenter latitude
        longitude: Epicenter longitude
        depth_km: Depth in kilometers
        url: USGS event detail URL
        felt: Number of "felt" reports (optional)
        alert: PAGER alert level (green/yellow/orange/red) (optional)
        tsunami: Whether tsunami warning was issued
        mag_type: Magnitude type (e.g., 'ml', 'md', 'mb')
    """
    id: str
    magnitude: float
    place: str
    time: datetime
    latitude: float
    longitude: float
    depth_km: float
    url: str
    felt: int | None = None
    alert: str | None = None
    tsunami: bool = False
    mag_type: str = "ml"

    @property
    def coordinates(self) -> tuple[float, float]:
        """Return (latitude, longitude) tuple."""
        return (self.latitude, self.longitude)


def parse_earthquake(feature: dict[str, Any]) -> Earthquake | None:
    """Parse a single GeoJSON feature into an Earthquake.

    Pure function: takes raw dict, returns typed Earthquake or None if invalid.

    Args:
        feature: GeoJSON feature dict from USGS API

    Returns:
        Earthquake object or None if parsing fails
    """
    try:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])

        if len(coords) < 3:
            return None

        # USGS uses milliseconds since epoch
        time_ms = props.get("time")
        if time_ms is None:
            return None

        event_time = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)

        magnitude = props.get("mag")
        if magnitude is None:
            return None

        return Earthquake(
            id=feature.get("id", ""),
            magnitude=float(magnitude),
            place=props.get("place", "Unknown location"),
            time=event_time,
            longitude=float(coords[0]),
            latitude=float(coords[1]),
            depth_km=float(coords[2]),
            url=props.get("url", ""),
            felt=props.get("felt"),
            alert=props.get("alert"),
            tsunami=bool(props.get("tsunami", 0)),
            mag_type=props.get("magType", "ml"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def parse_earthquakes(geojson: dict[str, Any]) -> list[Earthquake]:
    """Parse USGS GeoJSON response into list of Earthquakes.

    Pure function: filters out invalid features, returns valid earthquakes.

    Args:
        geojson: Full GeoJSON FeatureCollection from USGS API

    Returns:
        List of valid Earthquake objects, sorted by time (newest first)
    """
    features = geojson.get("features", [])
    earthquakes = []

    for feature in features:
        earthquake = parse_earthquake(feature)
        if earthquake is not None:
            earthquakes.append(earthquake)

    # Sort by time, newest first
    return sorted(earthquakes, key=lambda e: e.time, reverse=True)


def filter_by_magnitude(
    earthquakes: list[Earthquake],
    min_magnitude: float | None = None,
    max_magnitude: float | None = None,
) -> list[Earthquake]:
    """Filter earthquakes by magnitude range.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        min_magnitude: Minimum magnitude (inclusive), None for no minimum
        max_magnitude: Maximum magnitude (inclusive), None for no maximum

    Returns:
        Filtered list of earthquakes
    """
    result = earthquakes

    if min_magnitude is not None:
        result = [e for e in result if e.magnitude >= min_magnitude]

    if max_magnitude is not None:
        result = [e for e in result if e.magnitude <= max_magnitude]

    return result


def filter_by_time(
    earthquakes: list[Earthquake],
    after: datetime | None = None,
    before: datetime | None = None,
) -> list[Earthquake]:
    """Filter earthquakes by time range.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        after: Only include earthquakes after this time
        before: Only include earthquakes before this time

    Returns:
        Filtered list of earthquakes
    """
    result = earthquakes

    if after is not None:
        result = [e for e in result if e.time > after]

    if before is not None:
        result = [e for e in result if e.time < before]

    return result
