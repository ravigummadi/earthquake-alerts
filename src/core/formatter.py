"""Message formatting - Pure functions.

This module formats earthquake data into notification messages.
All functions are pure with no side effects.
"""

from dataclasses import dataclass
from datetime import timezone, timedelta
from typing import Any

from src.core.earthquake import Earthquake

# PST is UTC-8
PST = timezone(timedelta(hours=-8), name="PST")
from src.core.geo import PointOfInterest, get_distance_to_poi


def get_magnitude_emoji(magnitude: float) -> str:
    """Get an emoji representing earthquake severity.

    Pure function.
    """
    if magnitude >= 7.0:
        return "🚨"  # Major
    elif magnitude >= 6.0:
        return "⚠️"  # Strong
    elif magnitude >= 5.0:
        return "🔶"  # Moderate
    elif magnitude >= 4.0:
        return "🔸"  # Light
    else:
        return "🔹"  # Minor


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
    pst_time = earthquake.time.astimezone(PST)
    time_str = pst_time.strftime("%Y-%m-%d %H:%M:%S PST")
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
    # Convert earthquake time to Unix timestamp for Slack's local time formatting
    timestamp = int(earthquake.time.timestamp())

    # Google Maps link for the location
    maps_url = f"https://www.google.com/maps?q={earthquake.latitude},{earthquake.longitude}"

    # Build the main text with @everyone
    text = f"<!everyone> *{earthquake.magnitude:.1f}* - {earthquake.place}"

    # Build blocks for rich formatting
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{earthquake.magnitude:.1f}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{maps_url}|{earthquake.place}> at <!date^{timestamp}^{{time}}|{earthquake.time.strftime('%H:%M')}>",
            },
        },
    ]

    # Add special alerts
    special_alerts = []
    if earthquake.tsunami:
        special_alerts.append("🌊 *TSUNAMI WARNING ISSUED*")
    if earthquake.alert:
        alert_emoji = {
            "green": "🟢",
            "yellow": "🟡",
            "orange": "🟠",
            "red": "🔴",
        }.get(earthquake.alert, "⚪")
        special_alerts.append(f"{alert_emoji} PAGER Alert Level: {earthquake.alert.upper()}")
    if earthquake.felt:
        special_alerts.append(f"👥 Felt by {earthquake.felt} people")

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

    text = f"🌍 {count} earthquake(s) detected, max magnitude {max_mag:.1f}"

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
        pst_time = eq.time.astimezone(PST)
        time_str = pst_time.strftime("%H:%M PST")
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
