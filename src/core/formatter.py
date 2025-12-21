"""Message formatting - Pure functions.

This module formats earthquake data into notification messages.
All functions are pure with no side effects.
"""

from dataclasses import dataclass
from typing import Any

from src.core.earthquake import Earthquake
from src.core.geo import PointOfInterest, get_distance_to_poi


def get_magnitude_emoji(magnitude: float) -> str:
    """Get an emoji representing earthquake severity.

    Pure function.
    """
    if magnitude >= 7.0:
        return ":rotating_light:"  # Major
    elif magnitude >= 6.0:
        return ":warning:"  # Strong
    elif magnitude >= 5.0:
        return ":large_orange_diamond:"  # Moderate
    elif magnitude >= 4.0:
        return ":small_orange_diamond:"  # Light
    else:
        return ":small_blue_diamond:"  # Minor


def get_severity_label(magnitude: float) -> str:
    """Get a human-readable severity label.

    Pure function.
    """
    if magnitude >= 8.0:
        return "Great"
    elif magnitude >= 7.0:
        return "Major"
    elif magnitude >= 6.0:
        return "Strong"
    elif magnitude >= 5.0:
        return "Moderate"
    elif magnitude >= 4.0:
        return "Light"
    elif magnitude >= 3.0:
        return "Minor"
    else:
        return "Micro"


def format_earthquake_summary(earthquake: Earthquake) -> str:
    """Format a one-line summary of an earthquake.

    Pure function.

    Args:
        earthquake: Earthquake to summarize

    Returns:
        One-line summary string
    """
    time_str = earthquake.time.strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"M{earthquake.magnitude:.1f} - {earthquake.place} "
        f"at {time_str} (depth: {earthquake.depth_km:.1f}km)"
    )


def format_slack_message(
    earthquake: Earthquake,
    channel_name: str | None = None,
    nearby_pois: list[tuple[PointOfInterest, float]] | None = None,
) -> dict[str, Any]:
    """Format an earthquake as a Slack message payload.

    Pure function.

    Args:
        earthquake: Earthquake to format
        channel_name: Optional channel name for context
        nearby_pois: Optional list of (POI, distance_km) tuples

    Returns:
        Slack message payload dict
    """
    emoji = get_magnitude_emoji(earthquake.magnitude)
    severity = get_severity_label(earthquake.magnitude)
    time_str = earthquake.time.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build the main text
    text = f"{emoji} *{severity} Earthquake Detected*"

    # Build blocks for rich formatting
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {severity} Earthquake Detected",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Magnitude:*\n{earthquake.magnitude:.1f} {earthquake.mag_type.upper()}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Severity:*\n{severity}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Location:*\n{earthquake.place}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Depth:*\n{earthquake.depth_km:.1f} km",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{time_str}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Coordinates:*\n{earthquake.latitude:.4f}, {earthquake.longitude:.4f}",
                },
            ],
        },
    ]

    # Add special alerts
    special_alerts = []
    if earthquake.tsunami:
        special_alerts.append(":ocean: *TSUNAMI WARNING ISSUED*")
    if earthquake.alert:
        alert_emoji = {
            "green": ":green_circle:",
            "yellow": ":yellow_circle:",
            "orange": ":orange_circle:",
            "red": ":red_circle:",
        }.get(earthquake.alert, ":white_circle:")
        special_alerts.append(f"{alert_emoji} PAGER Alert Level: {earthquake.alert.upper()}")
    if earthquake.felt:
        special_alerts.append(f":busts_in_silhouette: Felt by {earthquake.felt} people")

    if special_alerts:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(special_alerts),
            },
        })

    # Add nearby POIs if provided
    if nearby_pois:
        poi_lines = []
        for poi, distance in nearby_pois:
            poi_lines.append(f"• {poi.name}: {distance:.1f} km away")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Nearby Locations:*\n" + "\n".join(poi_lines),
            },
        })

    # Add link to USGS
    if earthquake.url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View on USGS",
                    },
                    "url": earthquake.url,
                },
            ],
        })

    blocks.append({"type": "divider"})

    return {
        "text": text,
        "blocks": blocks,
    }


def format_batch_summary(earthquakes: list[Earthquake]) -> dict[str, Any]:
    """Format a summary of multiple earthquakes.

    Pure function.

    Args:
        earthquakes: List of earthquakes to summarize

    Returns:
        Slack message payload dict
    """
    if not earthquakes:
        return {
            "text": "No earthquakes to report.",
            "blocks": [],
        }

    count = len(earthquakes)
    max_mag = max(e.magnitude for e in earthquakes)

    text = f":earthquake: {count} earthquake(s) detected, max magnitude {max_mag:.1f}"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Earthquake Summary: {count} Events",
            },
        },
    ]

    # Add summary of each earthquake
    lines = []
    for eq in earthquakes[:10]:  # Limit to 10 for readability
        time_str = eq.time.strftime("%H:%M UTC")
        emoji = get_magnitude_emoji(eq.magnitude)
        lines.append(f"{emoji} M{eq.magnitude:.1f} - {eq.place} ({time_str})")

    if len(earthquakes) > 10:
        lines.append(f"_...and {len(earthquakes) - 10} more_")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "\n".join(lines),
        },
    })

    return {
        "text": text,
        "blocks": blocks,
    }


def get_nearby_pois(
    earthquake: Earthquake,
    pois: list[PointOfInterest],
    max_distance_km: float = 100.0,
) -> list[tuple[PointOfInterest, float]]:
    """Get POIs near an earthquake, sorted by distance.

    Pure function.

    Args:
        earthquake: The earthquake
        pois: List of points of interest
        max_distance_km: Maximum distance to include

    Returns:
        List of (POI, distance) tuples, sorted by distance
    """
    nearby = []
    for poi in pois:
        distance = get_distance_to_poi(earthquake, poi)
        if distance <= max_distance_km:
            nearby.append((poi, distance))

    return sorted(nearby, key=lambda x: x[1])
