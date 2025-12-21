"""Unit tests for earthquake parsing.

These tests demonstrate the benefit of the Functional Core pattern:
- No mocks needed
- Fast, deterministic execution
- Simple assertions on pure functions
"""

from datetime import datetime, timezone

import pytest

from src.core.earthquake import (
    Earthquake,
    parse_earthquake,
    parse_earthquakes,
    filter_by_magnitude,
    filter_by_time,
)


# Sample USGS GeoJSON feature for testing
SAMPLE_FEATURE = {
    "type": "Feature",
    "id": "nc75095866",
    "properties": {
        "mag": 4.2,
        "place": "10km NE of San Francisco, CA",
        "time": 1703001600000,  # 2023-12-19 12:00:00 UTC
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/nc75095866",
        "felt": 150,
        "alert": "green",
        "tsunami": 0,
        "magType": "ml",
    },
    "geometry": {
        "type": "Point",
        "coordinates": [-122.4194, 37.7749, 10.5],  # lon, lat, depth
    },
}

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "metadata": {"count": 1},
    "features": [SAMPLE_FEATURE],
}


class TestParseEarthquake:
    """Tests for parse_earthquake() pure function."""

    def test_parses_valid_feature(self):
        """Should parse a valid GeoJSON feature into Earthquake."""
        result = parse_earthquake(SAMPLE_FEATURE)

        assert result is not None
        assert result.id == "nc75095866"
        assert result.magnitude == 4.2
        assert result.place == "10km NE of San Francisco, CA"
        assert result.latitude == 37.7749
        assert result.longitude == -122.4194
        assert result.depth_km == 10.5
        assert result.felt == 150
        assert result.alert == "green"
        assert result.tsunami is False
        assert result.mag_type == "ml"

    def test_parses_time_correctly(self):
        """Should convert milliseconds to datetime."""
        result = parse_earthquake(SAMPLE_FEATURE)

        assert result is not None
        # 1703001600000 ms = 2023-12-19 12:00:00 UTC
        expected_time = datetime(2023, 12, 19, 12, 0, 0, tzinfo=timezone.utc)
        assert result.time == expected_time

    def test_returns_none_for_missing_magnitude(self):
        """Should return None if magnitude is missing."""
        feature = {
            "id": "test",
            "properties": {"place": "Test"},
            "geometry": {"coordinates": [0, 0, 0]},
        }
        result = parse_earthquake(feature)
        assert result is None

    def test_returns_none_for_missing_coordinates(self):
        """Should return None if coordinates are missing."""
        feature = {
            "id": "test",
            "properties": {"mag": 3.0, "time": 1703001600000},
            "geometry": {"coordinates": []},
        }
        result = parse_earthquake(feature)
        assert result is None

    def test_returns_none_for_missing_time(self):
        """Should return None if time is missing."""
        feature = {
            "id": "test",
            "properties": {"mag": 3.0},
            "geometry": {"coordinates": [0, 0, 0]},
        }
        result = parse_earthquake(feature)
        assert result is None

    def test_handles_empty_properties(self):
        """Should return None for empty properties."""
        feature = {"properties": {}, "geometry": {"coordinates": []}}
        result = parse_earthquake(feature)
        assert result is None


class TestParseEarthquakes:
    """Tests for parse_earthquakes() pure function."""

    def test_parses_geojson_response(self):
        """Should parse full GeoJSON response."""
        result = parse_earthquakes(SAMPLE_GEOJSON)

        assert len(result) == 1
        assert result[0].id == "nc75095866"

    def test_filters_invalid_features(self):
        """Should skip invalid features."""
        geojson = {
            "features": [
                SAMPLE_FEATURE,
                {"properties": {}, "geometry": {}},  # Invalid
            ]
        }
        result = parse_earthquakes(geojson)
        assert len(result) == 1

    def test_sorts_by_time_newest_first(self):
        """Should sort earthquakes by time, newest first."""
        older_feature = {
            **SAMPLE_FEATURE,
            "id": "older",
            "properties": {
                **SAMPLE_FEATURE["properties"],
                "time": 1702915200000,  # 1 day earlier
            },
        }
        geojson = {"features": [older_feature, SAMPLE_FEATURE]}

        result = parse_earthquakes(geojson)

        assert len(result) == 2
        assert result[0].id == "nc75095866"  # Newer first
        assert result[1].id == "older"

    def test_handles_empty_features(self):
        """Should return empty list for no features."""
        result = parse_earthquakes({"features": []})
        assert result == []

    def test_handles_missing_features(self):
        """Should return empty list if features key missing."""
        result = parse_earthquakes({})
        assert result == []


class TestFilterByMagnitude:
    """Tests for filter_by_magnitude() pure function."""

    @pytest.fixture
    def earthquakes(self):
        """Create test earthquakes with various magnitudes."""
        base = parse_earthquake(SAMPLE_FEATURE)
        assert base is not None

        return [
            Earthquake(**{**base.__dict__, "id": "m2", "magnitude": 2.0}),
            Earthquake(**{**base.__dict__, "id": "m4", "magnitude": 4.0}),
            Earthquake(**{**base.__dict__, "id": "m6", "magnitude": 6.0}),
        ]

    def test_filters_by_min_magnitude(self, earthquakes):
        """Should filter out earthquakes below minimum."""
        result = filter_by_magnitude(earthquakes, min_magnitude=4.0)

        assert len(result) == 2
        assert all(e.magnitude >= 4.0 for e in result)

    def test_filters_by_max_magnitude(self, earthquakes):
        """Should filter out earthquakes above maximum."""
        result = filter_by_magnitude(earthquakes, max_magnitude=4.0)

        assert len(result) == 2
        assert all(e.magnitude <= 4.0 for e in result)

    def test_filters_by_range(self, earthquakes):
        """Should filter to magnitude range."""
        result = filter_by_magnitude(earthquakes, min_magnitude=3.0, max_magnitude=5.0)

        assert len(result) == 1
        assert result[0].magnitude == 4.0

    def test_no_filter_returns_all(self, earthquakes):
        """Should return all if no filters specified."""
        result = filter_by_magnitude(earthquakes)
        assert len(result) == 3


class TestFilterByTime:
    """Tests for filter_by_time() pure function."""

    @pytest.fixture
    def earthquakes(self):
        """Create test earthquakes at different times."""
        base = parse_earthquake(SAMPLE_FEATURE)
        assert base is not None

        t1 = datetime(2023, 12, 19, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2023, 12, 19, 12, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2023, 12, 19, 14, 0, 0, tzinfo=timezone.utc)

        return [
            Earthquake(**{**base.__dict__, "id": "t1", "time": t1}),
            Earthquake(**{**base.__dict__, "id": "t2", "time": t2}),
            Earthquake(**{**base.__dict__, "id": "t3", "time": t3}),
        ]

    def test_filters_after_time(self, earthquakes):
        """Should filter earthquakes after given time."""
        cutoff = datetime(2023, 12, 19, 11, 0, 0, tzinfo=timezone.utc)
        result = filter_by_time(earthquakes, after=cutoff)

        assert len(result) == 2
        assert all(e.time > cutoff for e in result)

    def test_filters_before_time(self, earthquakes):
        """Should filter earthquakes before given time."""
        cutoff = datetime(2023, 12, 19, 13, 0, 0, tzinfo=timezone.utc)
        result = filter_by_time(earthquakes, before=cutoff)

        assert len(result) == 2
        assert all(e.time < cutoff for e in result)


class TestEarthquakeModel:
    """Tests for Earthquake dataclass."""

    def test_is_immutable(self):
        """Earthquake should be immutable (frozen)."""
        eq = parse_earthquake(SAMPLE_FEATURE)
        assert eq is not None

        with pytest.raises(Exception):  # FrozenInstanceError
            eq.magnitude = 5.0  # type: ignore

    def test_coordinates_property(self):
        """Should return (lat, lon) tuple."""
        eq = parse_earthquake(SAMPLE_FEATURE)
        assert eq is not None

        assert eq.coordinates == (37.7749, -122.4194)
