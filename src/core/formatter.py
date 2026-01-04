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
        action_buttons = [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View on USGS",
                },
                "url": earthquake.url,
            },
        ]

        # Only add Shakemap button if shakemap data is available
        if earthquake.has_shakemap:
            action_buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Shakemap",
                },
                "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{earthquake.id}/shakemap",
            })

        # Add earthquake.city link
        action_buttons.append({
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "earthquake.city",
            },
            "url": "https://earthquake.city/sanramon?from=alert",
        })

        blocks.append({
            "type": "actions",
            "elements": action_buttons,
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


def format_twitter_message(
    earthquake: Earthquake,
    nearby_pois: list[tuple[PointOfInterest, float]] | None = None,
) -> str:
    """Format an earthquake as a tweet (max 280 characters).

    Pure function.

    Prioritizes information in this order:
    1. Magnitude + location (required)
    2. Special alerts (tsunami, PAGER, felt reports)
    3. Nearest POI distance
    4. USGS link

    Args:
        earthquake: Earthquake to format
        nearby_pois: Optional list of (POI, distance_km) tuples

    Returns:
        Tweet text, guaranteed to be <= 280 characters
    """
    # Build tweet components
    lines = []

    # Line 1: Magnitude + location (always included)
    magnitude_prefix = ""
    if earthquake.magnitude >= 6.0:
        magnitude_prefix = "MAJOR "
    elif earthquake.magnitude >= 5.0:
        magnitude_prefix = "STRONG "

    headline = f"{magnitude_prefix}M{earthquake.magnitude:.1f} earthquake - {earthquake.place}"
    lines.append(headline)

    # Line 2: Special alerts (prioritize by importance)
    special_parts = []
    if earthquake.tsunami:
        special_parts.append("TSUNAMI WARNING")
    if earthquake.alert and earthquake.alert in ("orange", "red"):
        special_parts.append(f"PAGER: {earthquake.alert.upper()}")
    if earthquake.felt and earthquake.felt >= 100:
        if earthquake.felt >= 1000:
            special_parts.append(f"Felt by {earthquake.felt:,}+ people")
        else:
            special_parts.append(f"Felt by {earthquake.felt}+ people")

    if special_parts:
        lines.append(" | ".join(special_parts))

    # Line 3: Depth and/or nearest POI
    info_parts = []
    info_parts.append(f"Depth: {earthquake.depth_km:.0f}km")

    if nearby_pois:
        closest_poi, distance = nearby_pois[0]
        info_parts.append(f"{distance:.0f}km from {closest_poi.name}")

    lines.append(" | ".join(info_parts))

    # Line 4: Links (if space allows)
    usgs_link = earthquake.url or ""
    city_link = "https://earthquake.city/sanramon?from=alert"

    # Build tweet and check length
    tweet = "\n".join(lines)

    # Add links if they fit (prioritize earthquake.city as it's shorter)
    tweet_with_city = f"{tweet}\n{city_link}"
    if len(tweet_with_city) <= 280:
        tweet = tweet_with_city
        # Try to add USGS link too
        if usgs_link:
            tweet_with_both = f"{tweet}\n{usgs_link}"
            if len(tweet_with_both) <= 280:
                tweet = tweet_with_both
    elif usgs_link:
        # Fall back to just USGS if earthquake.city doesn't fit
        base_tweet = "\n".join(lines)
        tweet_with_usgs = f"{base_tweet}\n{usgs_link}"
        if len(tweet_with_usgs) <= 280:
            tweet = tweet_with_usgs

    # Truncate if still too long (shouldn't happen with good formatting)
    if len(tweet) > 280:
        # Truncate headline if needed
        max_headline_len = 280 - len("\n".join(lines[1:])) - 4  # 4 for "...\n"
        if max_headline_len > 20:
            lines[0] = lines[0][:max_headline_len] + "..."
            tweet = "\n".join(lines)
        else:
            # Last resort: just truncate the whole thing
            tweet = tweet[:277] + "..."

    return tweet


def format_whatsapp_message(
    earthquake: Earthquake,
    nearby_pois: list[tuple[PointOfInterest, float]] | None = None,
) -> str:
    """Format an earthquake as a WhatsApp message.

    Pure function.

    WhatsApp supports longer messages and emojis, so we include more detail
    than Twitter but keep it concise for mobile readability.

    Args:
        earthquake: Earthquake to format
        nearby_pois: Optional list of (POI, distance_km) tuples

    Returns:
        WhatsApp message text
    """
    emoji = get_magnitude_emoji(earthquake.magnitude)
    severity = get_severity_label(earthquake.magnitude)

    lines = []

    # Header with emoji and magnitude
    lines.append(f"{emoji} *{severity} Earthquake*")
    lines.append("")

    # Main info
    lines.append(f"*Magnitude:* {earthquake.magnitude:.1f}")
    lines.append(f"*Location:* {earthquake.place}")
    lines.append(f"*Depth:* {earthquake.depth_km:.1f} km")

    # Time in PST
    pst_time = earthquake.time.astimezone(PST)
    time_str = pst_time.strftime("%b %d, %Y at %I:%M %p PST")
    lines.append(f"*Time:* {time_str}")

    # Special alerts
    if earthquake.tsunami:
        lines.append("")
        lines.append("🌊 *TSUNAMI WARNING ISSUED*")

    if earthquake.alert:
        alert_emoji = {
            "green": "🟢",
            "yellow": "🟡",
            "orange": "🟠",
            "red": "🔴",
        }.get(earthquake.alert, "⚪")
        lines.append(f"{alert_emoji} PAGER Alert: {earthquake.alert.upper()}")

    if earthquake.felt and earthquake.felt >= 10:
        lines.append(f"👥 Felt by {earthquake.felt:,} people")

    # Nearby POIs
    if nearby_pois:
        lines.append("")
        lines.append("*Nearby Locations:*")
        for poi, distance in nearby_pois[:3]:  # Limit to 3
            lines.append(f"• {poi.name}: {distance:.1f} km away")

    # Links
    lines.append("")
    lines.append("🔗 https://earthquake.city/sanramon?from=alert")
    if earthquake.url:
        lines.append(f"🔗 {earthquake.url}")

    return "\n".join(lines)
