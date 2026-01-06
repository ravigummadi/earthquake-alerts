#!/usr/bin/env python3
"""Send test alerts to all configured channels.

⚠️  WARNING: This script sends REAL notifications to production channels!
    - Slack: Messages real channels
    - Twitter: Posts to @quake_alerts (PUBLIC!)
    - WhatsApp: Sends to real phone numbers

This script creates a synthetic test earthquake and sends alerts to configured
channels using the same formatting as production alerts. A [TEST] marker is added.

Usage:
    # Dry run (preview only, no sends)
    python scripts/send_test_alert.py --dry-run

    # Send to Slack only (safest for testing)
    python scripts/send_test_alert.py --slack-only

    # Send to specific channel
    python scripts/send_test_alert.py --channel earthquake-alerts

    # Send to ALL channels including Twitter (requires explicit flag)
    python scripts/send_test_alert.py --include-twitter

Environment:
    CONFIG_PATH: Path to config file (default: config/config-production.yaml)
    GCP_PROJECT: GCP project ID for Secret Manager access
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.earthquake import Earthquake
from src.core.formatter import (
    format_slack_message,
    format_twitter_message,
    format_whatsapp_message,
    get_nearby_pois,
)
from src.core.static_map import create_map_config
from src.shell.config_loader import load_config
from src.shell.slack_client import SlackClient
from src.shell.twitter_client import TwitterClient, TwitterCredentials
from src.shell.whatsapp_client import WhatsAppClient, WhatsAppCredentials
from src.shell.static_map_client import StaticMapClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def create_test_earthquake(
    magnitude: float = 5.5,
    location: str = "8km NE of San Ramon, CA",
    latitude: float = 37.8199,
    longitude: float = -121.9280,
) -> Earthquake:
    """Create a synthetic test earthquake.

    Args:
        magnitude: Earthquake magnitude
        location: Location description
        latitude: Epicenter latitude
        longitude: Epicenter longitude

    Returns:
        Synthetic Earthquake object
    """
    return Earthquake(
        id="test-earthquake-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        magnitude=magnitude,
        place=location,
        time=datetime.now(timezone.utc),
        latitude=latitude,
        longitude=longitude,
        depth_km=10.0,
        url="https://earthquake.usgs.gov/earthquakes/map/",
        felt=1250,  # Simulated felt reports
        alert="yellow",  # Simulated PAGER alert level
        tsunami=False,
        mag_type="ml",
        types="origin,phase-data",  # No shakemap for test
    )


def send_slack_alert(earthquake: Earthquake, channel, config) -> bool:
    """Send test alert to a Slack channel."""
    logger.info("Sending test alert to Slack channel: %s", channel.name)

    # Get nearby POIs
    nearby_pois = get_nearby_pois(
        earthquake,
        config.points_of_interest,
        max_distance_km=100,
    )

    # Format message using production formatter with is_test=True
    payload = format_slack_message(
        earthquake,
        channel_name=channel.name,
        nearby_pois=nearby_pois,
        is_test=True,
    )

    # Send via Slack client
    client = SlackClient()
    response = client.send_message(channel.webhook_url, payload)

    if response.success:
        logger.info("  ✓ Slack alert sent successfully")
        return True
    else:
        logger.error("  ✗ Failed to send Slack alert: %s", response.error)
        return False


def send_twitter_alert(earthquake: Earthquake, channel, config) -> bool:
    """Send test alert to Twitter.

    ⚠️  WARNING: This posts to a PUBLIC Twitter account!
    """
    logger.info("Sending test alert to Twitter channel: %s", channel.name)
    logger.warning("  ⚠️  This will post to PUBLIC Twitter account!")

    if not channel.credentials:
        logger.error("  ✗ Twitter channel has no credentials")
        return False

    # Convert credentials
    creds_dict = dict(channel.credentials)
    try:
        twitter_creds = TwitterCredentials(
            api_key=creds_dict["api_key"],
            api_secret=creds_dict["api_secret"],
            access_token=creds_dict["access_token"],
            access_token_secret=creds_dict["access_token_secret"],
        )
    except KeyError as e:
        logger.error("  ✗ Twitter credentials missing key: %s", e)
        return False

    # Get nearby POIs
    nearby_pois = get_nearby_pois(
        earthquake,
        config.points_of_interest,
        max_distance_km=100,
    )

    # Format tweet using production formatter with is_test=True
    tweet_text = format_twitter_message(
        earthquake,
        nearby_pois=nearby_pois,
        is_test=True,
    )
    logger.info("  Tweet text: %s", tweet_text[:100] + "..." if len(tweet_text) > 100 else tweet_text)

    # Generate map image
    twitter_client = TwitterClient()
    static_map_client = StaticMapClient()

    map_config = create_map_config(
        latitude=earthquake.latitude,
        longitude=earthquake.longitude,
        magnitude=earthquake.magnitude,
    )
    map_result = static_map_client.generate_map(map_config)

    media_ids = None
    if map_result.success and map_result.image_bytes:
        upload_result = twitter_client.upload_media(
            map_result.image_bytes,
            twitter_creds,
        )
        if upload_result.success and upload_result.media_id:
            media_ids = [upload_result.media_id]
            logger.info("  Map image uploaded: %s", upload_result.media_id)
        else:
            logger.warning("  Failed to upload map: %s", upload_result.error)
    else:
        logger.warning("  Failed to generate map: %s", map_result.error)

    # Post tweet
    response = twitter_client.send_tweet(tweet_text, twitter_creds, media_ids=media_ids)

    if response.success:
        logger.info("  ✓ Tweet posted successfully! ID: %s", response.tweet_id)
        return True
    else:
        logger.error("  ✗ Failed to post tweet: %s", response.error)
        return False


def send_whatsapp_alert(earthquake: Earthquake, channel, config) -> bool:
    """Send test alert via WhatsApp."""
    logger.info("Sending test alert to WhatsApp channel: %s", channel.name)

    if not channel.credentials:
        logger.error("  ✗ WhatsApp channel has no credentials")
        return False

    # Convert credentials
    creds_dict = dict(channel.credentials)
    try:
        whatsapp_creds = WhatsAppCredentials(
            account_sid=creds_dict["account_sid"],
            auth_token=creds_dict["auth_token"],
            from_number=creds_dict["from_number"],
        )
        to_numbers = creds_dict.get("to_numbers", ())
        if isinstance(to_numbers, str):
            to_numbers = (to_numbers,)
    except KeyError as e:
        logger.error("  ✗ WhatsApp credentials missing key: %s", e)
        return False

    if not to_numbers:
        logger.error("  ✗ WhatsApp channel has no recipients (to_numbers)")
        return False

    # Get nearby POIs
    nearby_pois = get_nearby_pois(
        earthquake,
        config.points_of_interest,
        max_distance_km=100,
    )

    # Format message using production formatter with is_test=True
    message_text = format_whatsapp_message(
        earthquake,
        nearby_pois=nearby_pois,
        is_test=True,
    )

    # Send to all recipients
    client = WhatsAppClient()
    responses = client.send_to_group(
        message_text,
        list(to_numbers),
        whatsapp_creds,
    )

    any_success = any(r.success for r in responses)
    if any_success:
        logger.info("  ✓ WhatsApp alert sent successfully to %d recipients", sum(1 for r in responses if r.success))
        return True
    else:
        errors = [r.error for r in responses if r.error]
        logger.error("  ✗ Failed to send WhatsApp alert: %s", "; ".join(errors))
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send test alerts to configured channels",
        epilog="⚠️  WARNING: This sends REAL notifications! Use --dry-run first.",
    )
    parser.add_argument(
        "--magnitude",
        type=float,
        default=5.5,
        help="Earthquake magnitude for test (default: 5.5)",
    )
    parser.add_argument(
        "--location",
        type=str,
        default="8km NE of San Ramon, CA",
        help="Location description (default: 8km NE of San Ramon, CA)",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=37.8199,
        help="Epicenter latitude (default: 37.8199)",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=-121.9280,
        help="Epicenter longitude (default: -121.9280)",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Send to specific channel name only (default: all non-Twitter channels)",
    )
    parser.add_argument(
        "--slack-only",
        action="store_true",
        help="Only send to Slack channels (safest option)",
    )
    parser.add_argument(
        "--include-twitter",
        action="store_true",
        help="Include Twitter channels (POSTS PUBLICLY - requires explicit opt-in)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without actually sending",
    )
    args = parser.parse_args()

    # Load configuration
    config_path = os.environ.get("CONFIG_PATH", "config/config-production.yaml")
    logger.info("Loading configuration from %s", config_path)
    config = load_config(config_path)

    if not config.alert_channels:
        logger.error("No alert channels configured")
        return 1

    # Create test earthquake
    earthquake = create_test_earthquake(
        magnitude=args.magnitude,
        location=args.location,
        latitude=args.latitude,
        longitude=args.longitude,
    )

    logger.info("")
    logger.info("Test Earthquake Details:")
    logger.info("  Magnitude: %.1f", earthquake.magnitude)
    logger.info("  Location: %s", earthquake.place)
    logger.info("  Coordinates: (%.4f, %.4f)", earthquake.latitude, earthquake.longitude)
    logger.info("  PAGER Alert: %s", earthquake.alert)
    logger.info("  Felt Reports: %d", earthquake.felt)
    logger.info("")

    # Filter channels based on flags
    channels = config.alert_channels

    # Apply channel filter if specified
    if args.channel:
        channels = [c for c in channels if c.name == args.channel]
        if not channels:
            logger.error("Channel '%s' not found in configuration", args.channel)
            return 1

    # Apply slack-only filter
    if args.slack_only:
        channels = [c for c in channels if c.channel_type == "slack"]
        if not channels:
            logger.error("No Slack channels found in configuration")
            return 1

    # Filter out Twitter unless explicitly included
    if not args.include_twitter and not args.channel:
        twitter_channels = [c for c in channels if c.channel_type == "twitter"]
        if twitter_channels:
            logger.warning("")
            logger.warning("⚠️  SKIPPING %d Twitter channel(s) - they post PUBLICLY!", len(twitter_channels))
            logger.warning("   To include Twitter, use: --include-twitter")
            logger.warning("")
        channels = [c for c in channels if c.channel_type != "twitter"]

    if not channels:
        logger.error("No channels to send to after filtering")
        return 1

    logger.info("Sending test alerts to %d channel(s)...", len(channels))
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - Would send to the following channels:")
        for channel in channels:
            marker = "⚠️ PUBLIC" if channel.channel_type == "twitter" else ""
            logger.info("  - %s (%s) %s", channel.name, channel.channel_type, marker)
        return 0

    # Send alerts to all channels
    results = []
    for channel in channels:
        if channel.channel_type == "twitter":
            success = send_twitter_alert(earthquake, channel, config)
        elif channel.channel_type == "whatsapp":
            success = send_whatsapp_alert(earthquake, channel, config)
        else:
            # Default to Slack
            success = send_slack_alert(earthquake, channel, config)

        results.append((channel.name, channel.channel_type, success))
        logger.info("")

    # Summary
    logger.info("=" * 50)
    logger.info("Test Alert Summary:")
    successes = sum(1 for _, _, s in results if s)
    failures = sum(1 for _, _, s in results if not s)
    logger.info("  Total channels: %d", len(results))
    logger.info("  Successful: %d", successes)
    logger.info("  Failed: %d", failures)

    for name, channel_type, success in results:
        status = "✓" if success else "✗"
        logger.info("  %s %s (%s)", status, name, channel_type)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
