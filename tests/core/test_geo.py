"""Unit tests for geographic calculations.

Pure function tests - no mocks needed, fast execution.
"""

import pytest

from src.core.geo import (
    BoundingBox,
    PointOfInterest,
    calculate_distance,
    is_within_bounds,
    is_within_radius,
    filter_by_bounds,
    filter_by_proximity,
    get_distance_to_poi,
    combine_bounds,
)
from src.core.earthquake import Earthquake
from datetime import datetime, timezone


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake for testing."""
    return Earthquake(
        id="test",
        magnitude=4.0,
        place="Test Location",
        time=datetime.now(timezone.utc),
        latitude=37.7749,
        longitude=-122.4194,
        depth_km=10.0,
        url="https://example.com",
    )


class TestCalculateDistance:
    """Tests for calculate_distance() Haversine implementation."""

    def test_same_point_returns_zero(self):
        """Distance from point to itself should be zero."""
        distance = calculate_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert distance == pytest.approx(0.0, abs=0.001)

    def test_known_distance_sf_to_la(self):
        """SF to LA should be approximately 559 km."""
        # San Francisco
        sf_lat, sf_lon = 37.7749, -122.4194
        # Los Angeles
        la_lat, la_lon = 34.0522, -118.2437

        distance = calculate_distance(sf_lat, sf_lon, la_lat, la_lon)

        # Approximate distance is 559 km
        assert distance == pytest.approx(559, rel=0.02)

    def test_known_distance_nyc_to_london(self):
        """NYC to London should be approximately 5570 km."""
        nyc_lat, nyc_lon = 40.7128, -74.0060
        london_lat, london_lon = 51.5074, -0.1278

        distance = calculate_distance(nyc_lat, nyc_lon, london_lat, london_lon)

        assert distance == pytest.approx(5570, rel=0.02)

    def test_symmetric(self):
        """Distance should be the same in both directions."""
        d1 = calculate_distance(37.7749, -122.4194, 34.0522, -118.2437)
        d2 = calculate_distance(34.0522, -118.2437, 37.7749, -122.4194)

        assert d1 == pytest.approx(d2, rel=0.001)


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_contains_point_inside(self):
        """Should return True for point inside box."""
        box = BoundingBox(
            min_latitude=35.0,
            max_latitude=40.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )
        assert box.contains(37.7749, -122.4194) is True

    def test_contains_point_outside(self):
        """Should return False for point outside box."""
        box = BoundingBox(
            min_latitude=35.0,
            max_latitude=40.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )
        # LA is outside this box
        assert box.contains(34.0522, -118.2437) is False

    def test_contains_point_on_boundary(self):
        """Should return True for point on boundary."""
        box = BoundingBox(
            min_latitude=35.0,
            max_latitude=40.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )
        assert box.contains(35.0, -122.0) is True


class TestIsWithinBounds:
    """Tests for is_within_bounds() function."""

    def test_earthquake_inside_bounds(self, sample_earthquake):
        """Should return True for earthquake inside bounds."""
        bounds = BoundingBox(
            min_latitude=35.0,
            max_latitude=40.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )
        assert is_within_bounds(sample_earthquake, bounds) is True

    def test_earthquake_outside_bounds(self, sample_earthquake):
        """Should return False for earthquake outside bounds."""
        bounds = BoundingBox(
            min_latitude=40.0,
            max_latitude=45.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )
        assert is_within_bounds(sample_earthquake, bounds) is False


class TestIsWithinRadius:
    """Tests for is_within_radius() function."""

    def test_earthquake_within_radius(self, sample_earthquake):
        """Should return True for earthquake within radius."""
        # Oakland is ~13km from SF
        oakland_lat, oakland_lon = 37.8044, -122.2712

        result = is_within_radius(
            sample_earthquake,
            oakland_lat,
            oakland_lon,
            radius_km=20,
        )
        assert result is True

    def test_earthquake_outside_radius(self, sample_earthquake):
        """Should return False for earthquake outside radius."""
        # LA is ~559km from SF
        la_lat, la_lon = 34.0522, -118.2437

        result = is_within_radius(
            sample_earthquake,
            la_lat,
            la_lon,
            radius_km=100,
        )
        assert result is False

    def test_earthquake_exactly_on_radius(self, sample_earthquake):
        """Should return True for earthquake exactly on radius."""
        # Find a point ~50km away
        result = is_within_radius(
            sample_earthquake,
            sample_earthquake.latitude,
            sample_earthquake.longitude,
            radius_km=0,
        )
        assert result is True  # Same point, distance is 0


class TestPointOfInterest:
    """Tests for PointOfInterest and related functions."""

    def test_get_distance_to_poi(self, sample_earthquake):
        """Should calculate correct distance to POI."""
        poi = PointOfInterest(
            name="Oakland Office",
            latitude=37.8044,
            longitude=-122.2712,
            alert_radius_km=50,
        )

        distance = get_distance_to_poi(sample_earthquake, poi)

        # SF to Oakland is approximately 13 km
        assert distance == pytest.approx(13, rel=0.1)


class TestFilterByBounds:
    """Tests for filter_by_bounds() function."""

    @pytest.fixture
    def earthquakes(self, sample_earthquake):
        """Create earthquakes in different locations."""
        return [
            sample_earthquake,  # SF
            Earthquake(
                **{
                    **sample_earthquake.__dict__,
                    "id": "la",
                    "latitude": 34.0522,
                    "longitude": -118.2437,
                }
            ),
        ]

    def test_filters_to_bounds(self, earthquakes):
        """Should return only earthquakes within bounds."""
        norcal_bounds = BoundingBox(
            min_latitude=35.0,
            max_latitude=40.0,
            min_longitude=-125.0,
            max_longitude=-120.0,
        )

        result = filter_by_bounds(earthquakes, norcal_bounds)

        assert len(result) == 1
        assert result[0].id == "test"  # SF


class TestFilterByProximity:
    """Tests for filter_by_proximity() function."""

    @pytest.fixture
    def earthquakes(self, sample_earthquake):
        """Create earthquakes at different distances from SF."""
        return [
            sample_earthquake,  # SF
            Earthquake(
                **{
                    **sample_earthquake.__dict__,
                    "id": "oakland",
                    "latitude": 37.8044,
                    "longitude": -122.2712,
                }
            ),
            Earthquake(
                **{
                    **sample_earthquake.__dict__,
                    "id": "la",
                    "latitude": 34.0522,
                    "longitude": -118.2437,
                }
            ),
        ]

    def test_filters_to_poi_radius(self, earthquakes):
        """Should return only earthquakes within POI radius."""
        poi = PointOfInterest(
            name="SF Office",
            latitude=37.7749,
            longitude=-122.4194,
            alert_radius_km=20,
        )

        result = filter_by_proximity(earthquakes, poi)

        # SF and Oakland are within 20km, LA is not
        assert len(result) == 2
        assert {e.id for e in result} == {"test", "oakland"}


class TestCombineBounds:
    """Tests for combine_bounds() function."""

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        result = combine_bounds([])
        assert result is None

    def test_single_box_returns_same(self):
        """Single box returns equivalent box."""
        box = BoundingBox(36.0, 38.0, -123.0, -121.0)
        result = combine_bounds([box])

        assert result == box

    def test_two_boxes_returns_encompassing(self):
        """Two boxes return their encompassing box."""
        box1 = BoundingBox(36.0, 38.0, -123.0, -121.0)  # NorCal
        box2 = BoundingBox(33.0, 35.0, -119.0, -117.0)  # SoCal

        result = combine_bounds([box1, box2])

        # Should encompass both
        assert result.min_latitude == 33.0
        assert result.max_latitude == 38.0
        assert result.min_longitude == -123.0
        assert result.max_longitude == -117.0

    def test_overlapping_boxes(self):
        """Overlapping boxes return correct combined box."""
        box1 = BoundingBox(36.0, 38.0, -123.0, -121.0)
        box2 = BoundingBox(37.0, 39.0, -122.0, -120.0)  # Overlaps

        result = combine_bounds([box1, box2])

        assert result.min_latitude == 36.0
        assert result.max_latitude == 39.0
        assert result.min_longitude == -123.0
        assert result.max_longitude == -120.0

    def test_three_boxes(self):
        """Three boxes return correct combined box."""
        boxes = [
            BoundingBox(36.0, 37.0, -123.0, -122.0),
            BoundingBox(37.0, 38.0, -122.0, -121.0),
            BoundingBox(38.0, 39.0, -121.0, -120.0),
        ]

        result = combine_bounds(boxes)

        assert result.min_latitude == 36.0
        assert result.max_latitude == 39.0
        assert result.min_longitude == -123.0
        assert result.max_longitude == -120.0


class TestPoiDistanceThresholdEdgeCases:
    """Edge cases for distance thresholds and boundary conditions in geo module."""

    def test_exact_distance_threshold_is_within_radius(self, sample_earthquake):
        """Earthquake at exactly the threshold distance is considered within radius."""
        target_lat = 37.8044
        target_lon = -122.2712
        actual_distance = calculate_distance(
            sample_earthquake.latitude,
            sample_earthquake.longitude,
            target_lat,
            target_lon,
        )

        # Exact distance threshold (inclusive <=)
        assert is_within_radius(
            sample_earthquake, target_lat, target_lon, radius_km=actual_distance
        ) is True

        # Just 1 millimeter below the actual distance
        assert is_within_radius(
            sample_earthquake, target_lat, target_lon, radius_km=actual_distance - 0.000001
        ) is False

        # Just 1 millimeter above the actual distance
        assert is_within_radius(
            sample_earthquake, target_lat, target_lon, radius_km=actual_distance + 0.000001
        ) is True

    def test_zero_radius_behavior(self, sample_earthquake):
        """A radius of 0.0 km matches identical point and rejects any offset."""
        # Identical point matches because distance is 0.0 <= 0.0
        assert is_within_radius(
            sample_earthquake,
            sample_earthquake.latitude,
            sample_earthquake.longitude,
            radius_km=0.0,
        ) is True

        # Offset by small fraction of degree (~11 meters) fails
        assert is_within_radius(
            sample_earthquake,
            sample_earthquake.latitude + 0.0001,
            sample_earthquake.longitude,
            radius_km=0.0,
        ) is False

    def test_filter_by_proximity_at_exact_threshold(self, sample_earthquake):
        """filter_by_proximity correctly includes exact boundary match and excludes offset."""
        poi_lat = 37.8
        poi_lon = -122.4
        exact_distance = calculate_distance(
            sample_earthquake.latitude,
            sample_earthquake.longitude,
            poi_lat,
            poi_lon,
        )

        poi = PointOfInterest("Target", poi_lat, poi_lon, alert_radius_km=exact_distance)

        earthquake_outside = Earthquake(
            **{
                **sample_earthquake.__dict__,
                "id": "slightly_outside",
                "latitude": sample_earthquake.latitude - 0.05,  # moves further south away from POI at 37.8
            }
        )

        result = filter_by_proximity([sample_earthquake, earthquake_outside], poi)
        assert len(result) == 1
        assert result[0].id == sample_earthquake.id

    def test_bounding_box_corners_and_edges(self):
        """BoundingBox.contains correctly treats all 4 edges and corners as inclusive."""
        box = BoundingBox(
            min_latitude=10.0,
            max_latitude=20.0,
            min_longitude=-120.0,
            max_longitude=-110.0,
        )

        # 4 corners
        assert box.contains(10.0, -120.0) is True
        assert box.contains(10.0, -110.0) is True
        assert box.contains(20.0, -120.0) is True
        assert box.contains(20.0, -110.0) is True

        # 4 edge midpoints
        assert box.contains(10.0, -115.0) is True  # South
        assert box.contains(20.0, -115.0) is True  # North
        assert box.contains(15.0, -120.0) is True  # West
        assert box.contains(15.0, -110.0) is True  # East

        # Points just outside each of the 4 borders
        assert box.contains(9.9999, -115.0) is False   # Just south
        assert box.contains(20.0001, -115.0) is False  # Just north
        assert box.contains(15.0, -120.0001) is False  # Just west
        assert box.contains(15.0, -109.9999) is False  # Just east
