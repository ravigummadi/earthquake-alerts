"""Unit tests for message formatting.

Pure function tests - no mocks needed.
"""

import pytest
from datetime import datetime, timezone

from src.core.earthquake import Earthquake
from src.core.geo import PointOfInterest
from src.core.formatter import (
    get_magnitude_emoji,
    get_severity_label,
    format_earthquake_summary,
    format_slack_message,
    format_batch_summary,
    get_nearby_pois,
)


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake for testing."""
    return Earthquake(
        id="test",
        magnitude=4.5,
        place="10km NE of San Francisco, CA",
        time=datetime(2023, 12, 19, 12, 0, 0, tzinfo=timezone.utc),
        latitude=37.7749,
        longitude=-122.4194,
        depth_km=10.5,
        url="https://earthquake.usgs.gov/earthquakes/eventpage/test",
        felt=150,
        alert="green",
        tsunami=False,
        mag_type="ml",
    )


class TestGetMagnitudeEmoji:
    """Tests for get_magnitude_emoji() function."""

    def test_major_earthquake(self):
        """M7+ should get rotating light."""
        assert get_magnitude_emoji(7.5) == ":rotating_light:"

    def test_strong_earthquake(self):
        """M6+ should get warning."""
        assert get_magnitude_emoji(6.2) == ":warning:"

    def test_moderate_earthquake(self):
        """M5+ should get large orange diamond."""
        assert get_magnitude_emoji(5.5) == ":large_orange_diamond:"

    def test_light_earthquake(self):
        """M4+ should get small orange diamond."""
        assert get_magnitude_emoji(4.5) == ":small_orange_diamond:"

    def test_minor_earthquake(self):
        """Below M4 should get small blue diamond."""
        assert get_magnitude_emoji(3.0) == ":small_blue_diamond:"


class TestGetSeverityLabel:
    """Tests for get_severity_label() function."""

    def test_great_earthquake(self):
        assert get_severity_label(8.0) == "Great"

    def test_major_earthquake(self):
        assert get_severity_label(7.0) == "Major"

    def test_strong_earthquake(self):
        assert get_severity_label(6.0) == "Strong"

    def test_moderate_earthquake(self):
        assert get_severity_label(5.0) == "Moderate"

    def test_light_earthquake(self):
        assert get_severity_label(4.0) == "Light"

    def test_minor_earthquake(self):
        assert get_severity_label(3.0) == "Minor"

    def test_micro_earthquake(self):
        assert get_severity_label(2.0) == "Micro"


class TestFormatEarthquakeSummary:
    """Tests for format_earthquake_summary() function."""

    def test_includes_magnitude(self, sample_earthquake):
        """Summary should include magnitude."""
        result = format_earthquake_summary(sample_earthquake)
        assert "M4.5" in result

    def test_includes_location(self, sample_earthquake):
        """Summary should include location."""
        result = format_earthquake_summary(sample_earthquake)
        assert "San Francisco" in result

    def test_includes_time(self, sample_earthquake):
        """Summary should include time."""
        result = format_earthquake_summary(sample_earthquake)
        assert "2023-12-19" in result

    def test_includes_depth(self, sample_earthquake):
        """Summary should include depth."""
        result = format_earthquake_summary(sample_earthquake)
        assert "10.5km" in result


class TestFormatSlackMessage:
    """Tests for format_slack_message() function."""

    def test_returns_dict_with_text(self, sample_earthquake):
        """Should return dict with text field."""
        result = format_slack_message(sample_earthquake)
        assert "text" in result
        assert "Earthquake" in result["text"]

    def test_returns_blocks(self, sample_earthquake):
        """Should return Slack blocks for rich formatting."""
        result = format_slack_message(sample_earthquake)
        assert "blocks" in result
        assert len(result["blocks"]) > 0

    def test_includes_magnitude_in_blocks(self, sample_earthquake):
        """Blocks should include magnitude."""
        result = format_slack_message(sample_earthquake)

        # Find section with fields
        sections = [b for b in result["blocks"] if b.get("type") == "section"]
        all_text = str(sections)
        assert "4.5" in all_text

    def test_includes_felt_when_present(self, sample_earthquake):
        """Should include felt reports when available."""
        result = format_slack_message(sample_earthquake)
        all_text = str(result["blocks"])
        assert "150" in all_text

    def test_includes_tsunami_warning(self, sample_earthquake):
        """Should include tsunami warning when present."""
        quake_with_tsunami = Earthquake(
            **{**sample_earthquake.__dict__, "tsunami": True}
        )
        result = format_slack_message(quake_with_tsunami)
        all_text = str(result["blocks"])
        assert "TSUNAMI" in all_text

    def test_includes_usgs_link(self, sample_earthquake):
        """Should include link to USGS."""
        result = format_slack_message(sample_earthquake)

        # Find action block with button
        actions = [b for b in result["blocks"] if b.get("type") == "actions"]
        assert len(actions) > 0
        assert "earthquake.usgs.gov" in str(actions)

    def test_includes_nearby_pois(self, sample_earthquake):
        """Should include nearby POIs when provided."""
        poi = PointOfInterest(
            name="Office",
            latitude=37.8,
            longitude=-122.4,
            alert_radius_km=50,
        )
        result = format_slack_message(
            sample_earthquake,
            nearby_pois=[(poi, 5.0)],
        )
        all_text = str(result["blocks"])
        assert "Office" in all_text
        assert "5.0 km" in all_text


class TestFormatBatchSummary:
    """Tests for format_batch_summary() function."""

    @pytest.fixture
    def earthquakes(self, sample_earthquake):
        """Create multiple earthquakes."""
        return [
            sample_earthquake,
            Earthquake(**{**sample_earthquake.__dict__, "id": "e2", "magnitude": 5.0}),
            Earthquake(**{**sample_earthquake.__dict__, "id": "e3", "magnitude": 3.0}),
        ]

    def test_returns_dict(self, earthquakes):
        """Should return Slack message dict."""
        result = format_batch_summary(earthquakes)
        assert "text" in result

    def test_includes_count(self, earthquakes):
        """Should include earthquake count."""
        result = format_batch_summary(earthquakes)
        assert "3" in result["text"]

    def test_includes_max_magnitude(self, earthquakes):
        """Should include maximum magnitude."""
        result = format_batch_summary(earthquakes)
        assert "5.0" in result["text"]

    def test_handles_empty_list(self):
        """Should handle empty earthquake list."""
        result = format_batch_summary([])
        assert "No earthquakes" in result["text"]


class TestGetNearbyPois:
    """Tests for get_nearby_pois() function."""

    @pytest.fixture
    def pois(self):
        """Create test POIs."""
        return [
            PointOfInterest("Close", 37.78, -122.41, alert_radius_km=50),
            PointOfInterest("Far", 34.0, -118.2, alert_radius_km=50),
        ]

    def test_returns_pois_within_distance(self, sample_earthquake, pois):
        """Should return POIs within max distance."""
        result = get_nearby_pois(sample_earthquake, pois, max_distance_km=50)

        assert len(result) == 1
        assert result[0][0].name == "Close"

    def test_returns_sorted_by_distance(self, sample_earthquake):
        """Should return POIs sorted by distance."""
        pois = [
            PointOfInterest("Far", 37.9, -122.5, alert_radius_km=50),
            PointOfInterest("Near", 37.775, -122.42, alert_radius_km=50),
        ]
        result = get_nearby_pois(sample_earthquake, pois, max_distance_km=100)

        assert result[0][0].name == "Near"
        assert result[1][0].name == "Far"

    def test_includes_distance(self, sample_earthquake, pois):
        """Should include distance in tuple."""
        result = get_nearby_pois(sample_earthquake, pois, max_distance_km=50)

        poi, distance = result[0]
        assert isinstance(distance, float)
        assert distance < 50
