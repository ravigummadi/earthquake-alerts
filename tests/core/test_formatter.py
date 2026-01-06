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
    format_twitter_message,
    format_whatsapp_message,
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
        """M7+ should get alert emoji."""
        assert get_magnitude_emoji(7.5) == "🚨"

    def test_strong_earthquake(self):
        """M6+ should get warning emoji."""
        assert get_magnitude_emoji(6.2) == "⚠️"

    def test_moderate_earthquake(self):
        """M5+ should get large orange diamond."""
        assert get_magnitude_emoji(5.5) == "🔶"

    def test_light_earthquake(self):
        """M4+ should get small orange diamond."""
        assert get_magnitude_emoji(4.5) == "🔸"

    def test_minor_earthquake(self):
        """Below M4 should get small blue diamond."""
        assert get_magnitude_emoji(3.0) == "🔹"


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
        assert "4.5" in result["text"]  # Magnitude in text
        assert "San Francisco" in result["text"]  # Location in text

    def test_returns_blocks(self, sample_earthquake):
        """Should return Slack blocks for rich formatting."""
        result = format_slack_message(sample_earthquake)
        assert "blocks" in result
        assert len(result["blocks"]) > 0

    def test_includes_magnitude_in_blocks(self, sample_earthquake):
        """Blocks should include magnitude."""
        result = format_slack_message(sample_earthquake)

        # Magnitude is in the header block
        all_text = str(result["blocks"])
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

    def test_includes_shakemap_button_when_available(self, sample_earthquake):
        """Should include Shakemap button when shakemap is available."""
        quake_with_shakemap = Earthquake(
            **{**sample_earthquake.__dict__, "types": ",origin,shakemap,phase-data,"}
        )
        result = format_slack_message(quake_with_shakemap)

        # Find action block with buttons
        actions = [b for b in result["blocks"] if b.get("type") == "actions"]
        assert len(actions) > 0
        action_str = str(actions)
        assert "Shakemap" in action_str
        assert "/shakemap" in action_str

    def test_excludes_shakemap_button_when_not_available(self, sample_earthquake):
        """Should not include Shakemap button when shakemap is not available."""
        # sample_earthquake has no types, so no shakemap
        result = format_slack_message(sample_earthquake)

        # Find action block with buttons
        actions = [b for b in result["blocks"] if b.get("type") == "actions"]
        assert len(actions) > 0
        action_str = str(actions)
        assert "View on USGS" in action_str
        assert "Shakemap" not in action_str

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

    def test_includes_test_marker_when_is_test_true(self, sample_earthquake):
        """Should include [TEST] marker when is_test=True."""
        result = format_slack_message(sample_earthquake, is_test=True)

        # Check text has [TEST]
        assert "[TEST]" in result["text"]

        # Check header block has [TEST]
        header_block = next(b for b in result["blocks"] if b.get("type") == "header")
        assert "[TEST]" in header_block["text"]["text"]

    def test_excludes_test_marker_when_is_test_false(self, sample_earthquake):
        """Should not include [TEST] marker when is_test=False."""
        result = format_slack_message(sample_earthquake, is_test=False)

        assert "[TEST]" not in result["text"]
        header_block = next(b for b in result["blocks"] if b.get("type") == "header")
        assert "[TEST]" not in header_block["text"]["text"]


class TestFormatTwitterMessage:
    """Tests for format_twitter_message() function."""

    def test_includes_magnitude_and_location(self, sample_earthquake):
        """Should include magnitude and location."""
        result = format_twitter_message(sample_earthquake)
        assert "M4.5" in result
        assert "San Francisco" in result

    def test_respects_280_char_limit(self, sample_earthquake):
        """Tweet should not exceed 280 characters."""
        result = format_twitter_message(sample_earthquake)
        assert len(result) <= 280

    def test_includes_test_marker_when_is_test_true(self, sample_earthquake):
        """Should include [TEST] marker when is_test=True."""
        result = format_twitter_message(sample_earthquake, is_test=True)
        assert "[TEST]" in result

    def test_excludes_test_marker_when_is_test_false(self, sample_earthquake):
        """Should not include [TEST] marker when is_test=False."""
        result = format_twitter_message(sample_earthquake, is_test=False)
        assert "[TEST]" not in result


class TestFormatWhatsAppMessage:
    """Tests for format_whatsapp_message() function."""

    def test_includes_magnitude_and_location(self, sample_earthquake):
        """Should include magnitude and location."""
        result = format_whatsapp_message(sample_earthquake)
        assert "4.5" in result
        assert "San Francisco" in result

    def test_includes_severity_label(self, sample_earthquake):
        """Should include severity label."""
        result = format_whatsapp_message(sample_earthquake)
        assert "Light Earthquake" in result  # M4.5 is "Light"

    def test_includes_test_marker_when_is_test_true(self, sample_earthquake):
        """Should include [TEST] marker when is_test=True."""
        result = format_whatsapp_message(sample_earthquake, is_test=True)
        assert "[TEST]" in result

    def test_excludes_test_marker_when_is_test_false(self, sample_earthquake):
        """Should not include [TEST] marker when is_test=False."""
        result = format_whatsapp_message(sample_earthquake, is_test=False)
        assert "[TEST]" not in result


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


class TestBackwardsCompatibility:
    """Tests ensuring backwards compatibility when modifying formatters.

    ⚠️  CRITICAL: These tests prevent breaking changes to the alert system.
    Any changes to formatter signatures MUST maintain backwards compatibility.
    """

    def test_format_slack_message_works_without_is_test(self, sample_earthquake):
        """format_slack_message must work without is_test parameter."""
        # This is how production code calls it - must not break!
        result = format_slack_message(sample_earthquake)
        assert "text" in result
        assert "blocks" in result
        # Default should NOT include [TEST]
        assert "[TEST]" not in result["text"]

    def test_format_slack_message_works_with_all_optional_params(self, sample_earthquake):
        """format_slack_message must accept all optional parameters."""
        poi = PointOfInterest("Test", 37.8, -122.4, alert_radius_km=50)
        result = format_slack_message(
            sample_earthquake,
            channel_name="test-channel",
            nearby_pois=[(poi, 5.0)],
            is_test=True,
        )
        assert "text" in result
        assert "[TEST]" in result["text"]

    def test_format_twitter_message_works_without_is_test(self, sample_earthquake):
        """format_twitter_message must work without is_test parameter."""
        result = format_twitter_message(sample_earthquake)
        assert isinstance(result, str)
        assert len(result) <= 280
        assert "[TEST]" not in result

    def test_format_twitter_message_works_with_all_optional_params(self, sample_earthquake):
        """format_twitter_message must accept all optional parameters."""
        poi = PointOfInterest("Test", 37.8, -122.4, alert_radius_km=50)
        result = format_twitter_message(
            sample_earthquake,
            nearby_pois=[(poi, 5.0)],
            is_test=True,
        )
        assert "[TEST]" in result

    def test_format_whatsapp_message_works_without_is_test(self, sample_earthquake):
        """format_whatsapp_message must work without is_test parameter."""
        result = format_whatsapp_message(sample_earthquake)
        assert isinstance(result, str)
        assert "[TEST]" not in result

    def test_format_whatsapp_message_works_with_all_optional_params(self, sample_earthquake):
        """format_whatsapp_message must accept all optional parameters."""
        poi = PointOfInterest("Test", 37.8, -122.4, alert_radius_km=50)
        result = format_whatsapp_message(
            sample_earthquake,
            nearby_pois=[(poi, 5.0)],
            is_test=True,
        )
        assert "[TEST]" in result


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_format_slack_message_with_none_felt(self):
        """Should handle earthquake with no felt reports."""
        earthquake = Earthquake(
            id="test",
            magnitude=3.0,
            place="Somewhere",
            time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            latitude=37.0,
            longitude=-122.0,
            depth_km=10.0,
            url="https://example.com",
            felt=None,  # No felt reports
            alert=None,  # No alert level
            tsunami=False,
        )
        result = format_slack_message(earthquake)
        assert "text" in result
        # Should not contain "Felt by" since felt is None
        all_text = str(result["blocks"])
        assert "Felt by" not in all_text

    def test_format_slack_message_with_no_url(self):
        """Should handle earthquake with empty URL."""
        earthquake = Earthquake(
            id="test",
            magnitude=3.0,
            place="Somewhere",
            time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            latitude=37.0,
            longitude=-122.0,
            depth_km=10.0,
            url="",  # Empty URL
        )
        result = format_slack_message(earthquake)
        assert "text" in result

    def test_format_twitter_message_with_long_location(self):
        """Should handle very long location strings without exceeding 280 chars."""
        earthquake = Earthquake(
            id="test",
            magnitude=5.5,
            place="A Very Long Location Name That Goes On And On And Describes The Exact Position In Great Detail Near San Francisco California USA",
            time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            latitude=37.0,
            longitude=-122.0,
            depth_km=10.0,
            url="https://earthquake.usgs.gov/earthquakes/eventpage/test",
        )
        result = format_twitter_message(earthquake)
        assert len(result) <= 280

    def test_format_whatsapp_message_with_all_alerts(self):
        """Should handle earthquake with tsunami and high PAGER alert."""
        earthquake = Earthquake(
            id="test",
            magnitude=7.5,
            place="Major Earthquake Zone",
            time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            latitude=37.0,
            longitude=-122.0,
            depth_km=10.0,
            url="https://example.com",
            felt=5000,
            alert="red",
            tsunami=True,
        )
        result = format_whatsapp_message(earthquake)
        assert "TSUNAMI" in result
        assert "RED" in result
        assert "5,000" in result  # Felt count formatted with comma

    def test_format_slack_message_with_empty_pois_list(self, sample_earthquake):
        """Should handle empty POI list gracefully."""
        result = format_slack_message(sample_earthquake, nearby_pois=[])
        assert "text" in result
        # Should not have "Nearby Locations" section
        all_text = str(result["blocks"])
        assert "Nearby Locations" not in all_text
