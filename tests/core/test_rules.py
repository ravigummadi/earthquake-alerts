"""Unit tests for alert rule evaluation.

Pure function tests - fast, no mocks needed.
"""

import pytest
from datetime import datetime, timezone

from src.core.earthquake import Earthquake
from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import (
    AlertRule,
    AlertChannel,
    evaluate_rule,
    evaluate_rules,
    filter_earthquakes_by_rules,
    make_alert_decisions,
)


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake for testing."""
    return Earthquake(
        id="test",
        magnitude=4.5,
        place="10km NE of San Francisco, CA",
        time=datetime.now(timezone.utc),
        latitude=37.7749,
        longitude=-122.4194,
        depth_km=10.0,
        url="https://example.com",
        felt=100,
        alert="green",
        tsunami=False,
    )


@pytest.fixture
def bay_area_bounds():
    """Bounding box for SF Bay Area."""
    return BoundingBox(
        min_latitude=35.9,
        max_latitude=39.2,
        min_longitude=-122.9,
        max_longitude=-120.7,
    )


class TestEvaluateRule:
    """Tests for evaluate_rule() pure function."""

    def test_magnitude_above_threshold(self, sample_earthquake):
        """Should match when magnitude is above threshold."""
        rule = AlertRule(min_magnitude=4.0)
        assert evaluate_rule(sample_earthquake, rule) is True

    def test_magnitude_below_threshold(self, sample_earthquake):
        """Should not match when magnitude is below threshold."""
        rule = AlertRule(min_magnitude=5.0)
        assert evaluate_rule(sample_earthquake, rule) is False

    def test_magnitude_at_threshold(self, sample_earthquake):
        """Should match when magnitude equals threshold."""
        rule = AlertRule(min_magnitude=4.5)
        assert evaluate_rule(sample_earthquake, rule) is True

    def test_max_magnitude_filter(self, sample_earthquake):
        """Should not match when above max magnitude."""
        rule = AlertRule(min_magnitude=0, max_magnitude=4.0)
        assert evaluate_rule(sample_earthquake, rule) is False

    def test_within_bounds(self, sample_earthquake, bay_area_bounds):
        """Should match when earthquake is within bounds."""
        rule = AlertRule(min_magnitude=0, bounds=bay_area_bounds)
        assert evaluate_rule(sample_earthquake, rule) is True

    def test_outside_bounds(self, sample_earthquake):
        """Should not match when earthquake is outside bounds."""
        socal_bounds = BoundingBox(
            min_latitude=32.0,
            max_latitude=35.0,
            min_longitude=-120.0,
            max_longitude=-115.0,
        )
        rule = AlertRule(min_magnitude=0, bounds=socal_bounds)
        assert evaluate_rule(sample_earthquake, rule) is False

    def test_within_poi_radius(self, sample_earthquake):
        """Should match when within POI alert radius."""
        poi = PointOfInterest(
            name="Office",
            latitude=37.8,
            longitude=-122.4,
            alert_radius_km=50,
        )
        rule = AlertRule(min_magnitude=0, points_of_interest=(poi,))
        assert evaluate_rule(sample_earthquake, rule) is True

    def test_outside_poi_radius(self, sample_earthquake):
        """Should not match when outside POI alert radius."""
        poi = PointOfInterest(
            name="LA Office",
            latitude=34.0,
            longitude=-118.2,
            alert_radius_km=50,
        )
        rule = AlertRule(min_magnitude=0, points_of_interest=(poi,))
        assert evaluate_rule(sample_earthquake, rule) is False

    def test_tsunami_warning_bypasses_magnitude(self, sample_earthquake):
        """Tsunami warning should trigger alert regardless of magnitude."""
        earthquake_with_tsunami = Earthquake(
            **{**sample_earthquake.__dict__, "magnitude": 2.0, "tsunami": True}
        )
        rule = AlertRule(min_magnitude=5.0, alert_on_tsunami=True)
        assert evaluate_rule(earthquake_with_tsunami, rule) is True

    def test_felt_reports_bypasses_magnitude(self, sample_earthquake):
        """High felt reports should trigger alert."""
        highly_felt = Earthquake(
            **{**sample_earthquake.__dict__, "magnitude": 2.0, "felt": 500}
        )
        rule = AlertRule(
            min_magnitude=5.0,
            alert_on_felt=True,
            felt_threshold=100,
        )
        assert evaluate_rule(highly_felt, rule) is True

    def test_no_location_restriction_matches_all(self, sample_earthquake):
        """Rule with no bounds or POIs should match any location."""
        rule = AlertRule(min_magnitude=0)
        assert evaluate_rule(sample_earthquake, rule) is True


class TestEvaluateRules:
    """Tests for evaluate_rules() function."""

    @pytest.fixture
    def channels(self, bay_area_bounds):
        """Create test channels with different rules."""
        return [
            AlertChannel(
                name="critical",
                channel_type="slack",
                webhook_url="https://hooks.slack.com/critical",
                rules=AlertRule(min_magnitude=5.0, bounds=bay_area_bounds),
            ),
            AlertChannel(
                name="all-alerts",
                channel_type="slack",
                webhook_url="https://hooks.slack.com/all",
                rules=AlertRule(min_magnitude=2.0, bounds=bay_area_bounds),
            ),
        ]

    def test_matches_multiple_channels(self, sample_earthquake, channels):
        """Should return all matching channels."""
        # M4.5 matches all-alerts but not critical
        result = evaluate_rules(sample_earthquake, channels)

        assert len(result) == 1
        assert result[0].name == "all-alerts"

    def test_large_earthquake_matches_all(self, sample_earthquake, channels):
        """Large earthquake should match all channels."""
        big_quake = Earthquake(
            **{**sample_earthquake.__dict__, "magnitude": 6.0}
        )
        result = evaluate_rules(big_quake, channels)

        assert len(result) == 2

    def test_small_earthquake_matches_none(self, sample_earthquake, channels):
        """Small earthquake should match no channels."""
        small_quake = Earthquake(
            **{**sample_earthquake.__dict__, "magnitude": 1.5}
        )
        result = evaluate_rules(small_quake, channels)

        assert len(result) == 0


class TestFilterEarthquakesByRules:
    """Tests for filter_earthquakes_by_rules() function."""

    @pytest.fixture
    def earthquakes(self, sample_earthquake):
        """Create earthquakes of various magnitudes."""
        return [
            Earthquake(**{**sample_earthquake.__dict__, "id": "m2", "magnitude": 2.0}),
            Earthquake(**{**sample_earthquake.__dict__, "id": "m4", "magnitude": 4.0}),
            Earthquake(**{**sample_earthquake.__dict__, "id": "m6", "magnitude": 6.0}),
        ]

    def test_filters_by_rule(self, earthquakes):
        """Should filter earthquakes matching the rule."""
        rule = AlertRule(min_magnitude=4.0)
        result = filter_earthquakes_by_rules(earthquakes, rule)

        assert len(result) == 2
        assert {e.id for e in result} == {"m4", "m6"}


class TestMakeAlertDecisions:
    """Tests for make_alert_decisions() function."""

    @pytest.fixture
    def channels(self, bay_area_bounds):
        """Create test channels."""
        return [
            AlertChannel(
                name="major",
                channel_type="slack",
                webhook_url="https://hooks.slack.com/major",
                rules=AlertRule(min_magnitude=5.0, bounds=bay_area_bounds),
            ),
            AlertChannel(
                name="all",
                channel_type="slack",
                webhook_url="https://hooks.slack.com/all",
                rules=AlertRule(min_magnitude=3.0, bounds=bay_area_bounds),
            ),
        ]

    @pytest.fixture
    def earthquakes(self, sample_earthquake):
        """Create test earthquakes."""
        return [
            Earthquake(**{**sample_earthquake.__dict__, "id": "m2", "magnitude": 2.0}),
            Earthquake(**{**sample_earthquake.__dict__, "id": "m4", "magnitude": 4.0}),
            Earthquake(**{**sample_earthquake.__dict__, "id": "m6", "magnitude": 6.0}),
        ]

    def test_returns_decisions_for_matching_earthquakes(self, earthquakes, channels):
        """Should return decisions for earthquakes matching at least one channel."""
        decisions = make_alert_decisions(earthquakes, channels)

        # M2 matches nothing, M4 matches 'all', M6 matches both
        assert len(decisions) == 2

    def test_decision_contains_matching_channels(self, earthquakes, channels):
        """Each decision should contain all matching channels."""
        decisions = make_alert_decisions(earthquakes, channels)

        m6_decision = next(d for d in decisions if d.earthquake.id == "m6")
        assert len(m6_decision.channels) == 2

        m4_decision = next(d for d in decisions if d.earthquake.id == "m4")
        assert len(m4_decision.channels) == 1
        assert m4_decision.channels[0].name == "all"

    def test_should_alert_property(self, earthquakes, channels):
        """AlertDecision.should_alert should be True when channels exist."""
        decisions = make_alert_decisions(earthquakes, channels)

        assert all(d.should_alert for d in decisions)
