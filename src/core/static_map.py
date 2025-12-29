"""Static map configuration - Pure functions.

This module provides pure functions for generating static map parameters.
The actual image generation (I/O) is handled by the shell layer.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MapConfig:
    """Immutable configuration for a static map image.

    Attributes:
        latitude: Center latitude
        longitude: Center longitude
        zoom: Zoom level (1-18)
        width: Image width in pixels
        height: Image height in pixels
        marker_color: Hex color for the epicenter marker
        marker_radius: Radius of the marker circle in pixels
    """
    latitude: float
    longitude: float
    zoom: int
    width: int
    height: int
    marker_color: str
    marker_radius: int


def get_magnitude_color(magnitude: float) -> str:
    """Get hex color for magnitude visualization.

    Pure function. Matches the colors used on earthquake.city.

    Args:
        magnitude: Earthquake magnitude

    Returns:
        Hex color string (e.g., "#dc2626")
    """
    if magnitude >= 7.0:
        return "#dc2626"  # red-600 (severe)
    elif magnitude >= 5.0:
        return "#f97316"  # orange-500 (high)
    elif magnitude >= 3.0:
        return "#eab308"  # yellow-500 (medium)
    return "#22c55e"  # green-500 (low)


def get_zoom_level(magnitude: float) -> int:
    """Determine appropriate map zoom level based on magnitude.

    Pure function. Larger earthquakes get zoomed out to show more context.

    Args:
        magnitude: Earthquake magnitude

    Returns:
        Zoom level (1-18)
    """
    if magnitude >= 7.0:
        return 7  # Wide view for major earthquakes
    elif magnitude >= 6.0:
        return 8
    elif magnitude >= 5.0:
        return 9
    elif magnitude >= 4.0:
        return 10
    return 11  # Closer view for smaller earthquakes


def get_marker_radius(magnitude: float) -> int:
    """Determine marker radius based on magnitude.

    Pure function. Larger earthquakes get bigger markers.

    Args:
        magnitude: Earthquake magnitude

    Returns:
        Marker radius in pixels
    """
    # Scale radius with magnitude (roughly 8-20 pixels)
    base_radius = 8
    scale_factor = 2
    return min(int(base_radius + magnitude * scale_factor), 24)


def create_map_config(
    latitude: float,
    longitude: float,
    magnitude: float,
    width: int = 800,
    height: int = 400,
) -> MapConfig:
    """Create map configuration for an earthquake.

    Pure function. Determines zoom, color, and marker size based on magnitude.

    Args:
        latitude: Epicenter latitude
        longitude: Epicenter longitude
        magnitude: Earthquake magnitude
        width: Image width in pixels (default: 800)
        height: Image height in pixels (default: 400)

    Returns:
        MapConfig with all parameters set
    """
    return MapConfig(
        latitude=latitude,
        longitude=longitude,
        zoom=get_zoom_level(magnitude),
        width=width,
        height=height,
        marker_color=get_magnitude_color(magnitude),
        marker_radius=get_marker_radius(magnitude),
    )
