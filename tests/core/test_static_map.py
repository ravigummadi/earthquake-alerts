"""Tests for static map configuration - Pure functions.

These are fast unit tests with no mocks needed since they test pure functions.
"""

import pytest

from src.core.static_map import (
    MapConfig,
    get_magnitude_color,
    get_zoom_level,
    get_marker_radius,
    create_map_config,
)


class TestGetMagnitudeColor:
    """Tests for get_magnitude_color()."""

    def test_severe_earthquake_is_red(self):
        """Magnitude >= 7.0 returns red color."""
        assert get_magnitude_color(7.0) == "#dc2626"
        assert get_magnitude_color(8.5) == "#dc2626"

    def test_high_magnitude_is_orange(self):
        """Magnitude 5.0-6.9 returns orange color."""
        assert get_magnitude_color(5.0) == "#f97316"
        assert get_magnitude_color(6.9) == "#f97316"

    def test_medium_magnitude_is_yellow(self):
        """Magnitude 3.0-4.9 returns yellow color."""
        assert get_magnitude_color(3.0) == "#eab308"
        assert get_magnitude_color(4.9) == "#eab308"

    def test_low_magnitude_is_green(self):
        """Magnitude < 3.0 returns green color."""
        assert get_magnitude_color(2.9) == "#22c55e"
        assert get_magnitude_color(1.0) == "#22c55e"


class TestGetZoomLevel:
    """Tests for get_zoom_level()."""

    def test_major_earthquake_zooms_out(self):
        """Magnitude >= 7.0 gets wide view."""
        assert get_zoom_level(7.0) == 7
        assert get_zoom_level(8.5) == 7

    def test_strong_earthquake_moderate_zoom(self):
        """Magnitude 6.0-6.9 gets moderate zoom out."""
        assert get_zoom_level(6.0) == 8
        assert get_zoom_level(6.9) == 8

    def test_moderate_earthquake_closer_zoom(self):
        """Magnitude 5.0-5.9 gets closer zoom."""
        assert get_zoom_level(5.0) == 9
        assert get_zoom_level(5.9) == 9

    def test_light_earthquake_standard_zoom(self):
        """Magnitude 4.0-4.9 gets standard zoom."""
        assert get_zoom_level(4.0) == 10
        assert get_zoom_level(4.9) == 10

    def test_minor_earthquake_close_zoom(self):
        """Magnitude < 4.0 gets closest zoom."""
        assert get_zoom_level(3.5) == 11
        assert get_zoom_level(2.0) == 11


class TestGetMarkerRadius:
    """Tests for get_marker_radius()."""

    def test_radius_scales_with_magnitude(self):
        """Marker radius increases with magnitude."""
        assert get_marker_radius(2.0) < get_marker_radius(5.0)
        assert get_marker_radius(5.0) < get_marker_radius(7.0)

    def test_radius_has_minimum(self):
        """Small earthquakes still have visible marker."""
        assert get_marker_radius(1.0) >= 8

    def test_radius_has_maximum(self):
        """Large earthquakes don't have oversized marker."""
        assert get_marker_radius(9.0) <= 24
        assert get_marker_radius(10.0) <= 24


class TestCreateMapConfig:
    """Tests for create_map_config()."""

    def test_returns_map_config(self):
        """Returns a MapConfig dataclass."""
        config = create_map_config(
            latitude=37.78,
            longitude=-122.42,
            magnitude=4.5,
        )
        assert isinstance(config, MapConfig)

    def test_sets_coordinates(self):
        """Coordinates are set correctly."""
        config = create_map_config(
            latitude=37.78,
            longitude=-122.42,
            magnitude=4.5,
        )
        assert config.latitude == 37.78
        assert config.longitude == -122.42

    def test_uses_default_dimensions(self):
        """Default dimensions are 800x400."""
        config = create_map_config(
            latitude=37.78,
            longitude=-122.42,
            magnitude=4.5,
        )
        assert config.width == 800
        assert config.height == 400

    def test_accepts_custom_dimensions(self):
        """Custom dimensions are respected."""
        config = create_map_config(
            latitude=37.78,
            longitude=-122.42,
            magnitude=4.5,
            width=1200,
            height=600,
        )
        assert config.width == 1200
        assert config.height == 600

    def test_calculates_zoom_from_magnitude(self):
        """Zoom level is calculated based on magnitude."""
        config_small = create_map_config(37.78, -122.42, 3.0)
        config_large = create_map_config(37.78, -122.42, 7.0)
        # Larger earthquakes should have lower zoom (more zoomed out)
        assert config_large.zoom < config_small.zoom

    def test_calculates_color_from_magnitude(self):
        """Color is calculated based on magnitude."""
        config_low = create_map_config(37.78, -122.42, 2.5)
        config_high = create_map_config(37.78, -122.42, 7.5)
        assert config_low.marker_color == "#22c55e"  # green
        assert config_high.marker_color == "#dc2626"  # red

    def test_calculates_marker_radius_from_magnitude(self):
        """Marker radius is calculated based on magnitude."""
        config_small = create_map_config(37.78, -122.42, 2.0)
        config_large = create_map_config(37.78, -122.42, 7.0)
        assert config_large.marker_radius > config_small.marker_radius


class TestMapConfig:
    """Tests for MapConfig dataclass."""

    def test_is_immutable(self):
        """MapConfig is frozen (immutable)."""
        config = MapConfig(
            latitude=37.78,
            longitude=-122.42,
            zoom=10,
            width=800,
            height=400,
            marker_color="#dc2626",
            marker_radius=12,
        )
        with pytest.raises(AttributeError):
            config.latitude = 38.0
