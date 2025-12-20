"""Alert rule evaluation - Pure functions.

This module evaluates which earthquakes should trigger alerts based on
configurable rules. All functions are pure with no side effects.
"""

from dataclasses import dataclass, field

from src.core.earthquake import Earthquake
from src.core.geo import BoundingBox, PointOfInterest, is_within_bounds, is_within_radius


@dataclass(frozen=True)
class AlertRule:
    """Configuration for when to trigger alerts.

    Attributes:
        min_magnitude: Minimum magnitude to alert on (inclusive)
        max_magnitude: Maximum magnitude (inclusive), None for no limit
        bounds: Geographic bounding box (optional)
        points_of_interest: List of POIs for proximity alerts
        alert_on_tsunami: Always alert if tsunami warning
        alert_on_felt: Alert if felt reports exceed threshold
        felt_threshold: Minimum felt reports to trigger alert
    """
    min_magnitude: float = 0.0
    max_magnitude: float | None = None
    bounds: BoundingBox | None = None
    points_of_interest: tuple[PointOfInterest, ...] = field(default_factory=tuple)
    alert_on_tsunami: bool = True
    alert_on_felt: bool = False
    felt_threshold: int = 10


@dataclass(frozen=True)
class AlertChannel:
    """A notification channel with its rules.

    Attributes:
        name: Channel identifier
        channel_type: Type of channel (e.g., 'slack', 'discord')
        webhook_url: Webhook URL for notifications
        rules: Alert rules for this channel
    """
    name: str
    channel_type: str
    webhook_url: str
    rules: AlertRule


def matches_magnitude_rule(earthquake: Earthquake, rule: AlertRule) -> bool:
    """Check if earthquake magnitude matches rule criteria.

    Pure function.
    """
    if earthquake.magnitude < rule.min_magnitude:
        return False

    if rule.max_magnitude is not None and earthquake.magnitude > rule.max_magnitude:
        return False

    return True


def matches_location_rule(earthquake: Earthquake, rule: AlertRule) -> bool:
    """Check if earthquake location matches rule criteria.

    Pure function.

    Returns True if:
    - No bounds specified (matches all locations), OR
    - Earthquake is within bounds, OR
    - Earthquake is within any POI's alert radius
    """
    # If no location restrictions, match all
    if rule.bounds is None and not rule.points_of_interest:
        return True

    # Check bounding box
    if rule.bounds is not None and is_within_bounds(earthquake, rule.bounds):
        return True

    # Check points of interest
    for poi in rule.points_of_interest:
        if is_within_radius(
            earthquake, poi.latitude, poi.longitude, poi.alert_radius_km
        ):
            return True

    return False


def matches_special_conditions(earthquake: Earthquake, rule: AlertRule) -> bool:
    """Check if earthquake matches special alert conditions.

    Pure function.

    These conditions can trigger alerts even if magnitude is below threshold:
    - Tsunami warning
    - High number of felt reports
    """
    if rule.alert_on_tsunami and earthquake.tsunami:
        return True

    if rule.alert_on_felt:
        felt = earthquake.felt or 0
        if felt >= rule.felt_threshold:
            return True

    return False


def evaluate_rule(earthquake: Earthquake, rule: AlertRule) -> bool:
    """Evaluate if an earthquake matches alert rule criteria.

    Pure function.

    Args:
        earthquake: Earthquake to evaluate
        rule: Alert rule to check against

    Returns:
        True if earthquake should trigger an alert for this rule
    """
    # Special conditions can override magnitude check
    if matches_special_conditions(earthquake, rule):
        return matches_location_rule(earthquake, rule)

    # Standard check: magnitude AND location
    return matches_magnitude_rule(earthquake, rule) and matches_location_rule(earthquake, rule)


def evaluate_rules(
    earthquake: Earthquake,
    channels: list[AlertChannel],
) -> list[AlertChannel]:
    """Determine which channels should receive an alert for an earthquake.

    Pure function.

    Args:
        earthquake: Earthquake to evaluate
        channels: List of channels with their rules

    Returns:
        List of channels that should receive an alert
    """
    return [
        channel for channel in channels
        if evaluate_rule(earthquake, channel.rules)
    ]


def filter_earthquakes_by_rules(
    earthquakes: list[Earthquake],
    rule: AlertRule,
) -> list[Earthquake]:
    """Filter earthquakes to only those matching a rule.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        rule: Rule to filter by

    Returns:
        Earthquakes that match the rule
    """
    return [e for e in earthquakes if evaluate_rule(e, rule)]


@dataclass(frozen=True)
class AlertDecision:
    """Result of evaluating an earthquake against all channels.

    Attributes:
        earthquake: The earthquake evaluated
        channels: Channels that should receive an alert
    """
    earthquake: Earthquake
    channels: list[AlertChannel]

    @property
    def should_alert(self) -> bool:
        """Returns True if at least one channel should receive an alert."""
        return len(self.channels) > 0


def make_alert_decisions(
    earthquakes: list[Earthquake],
    channels: list[AlertChannel],
) -> list[AlertDecision]:
    """Make alert decisions for all earthquakes.

    Pure function.

    Args:
        earthquakes: Earthquakes to evaluate
        channels: All configured channels

    Returns:
        Alert decisions for earthquakes that should trigger at least one alert
    """
    decisions = []

    for earthquake in earthquakes:
        matching_channels = evaluate_rules(earthquake, channels)
        if matching_channels:
            decisions.append(AlertDecision(
                earthquake=earthquake,
                channels=matching_channels,
            ))

    return decisions
