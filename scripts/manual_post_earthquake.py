#!/usr/bin/env python3
"""Manual earthquake posting script.

This script allows manually posting an earthquake to Twitter/X
that may have been missed due to deduplication or other issues.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shell.usgs_client import USGSClient
from src.shell.twitter_client import TwitterClient, TwitterCredentials
from src.shell.static_map_client import StaticMapClient
from src.shell.config_loader import load_config
from src.core.earthquake import parse_earthquakes
from src.core.formatter import format_twitter_message, get_nearby_pois
from src.core.static_map import create_map_config
from src.core.geo import BoundingBox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_earthquake_by_magnitude(
    target_magnitude: float,
    tolerance: float = 0.05,
    hours_back: int = 48,
) -> list:
    """Find earthquakes matching a target magnitude."""
    # Use the same bounds as production config
    bounds = BoundingBox(
        min_latitude=37.3,
        max_latitude=38.3,
        min_longitude=-122.5,
        max_longitude=-121.5,
    )

    client = USGSClient()
    geojson = client.fetch_recent(
        bounds=bounds,
        min_magnitude=2.0,
        hours=hours_back,
    )

    earthquakes = parse_earthquakes(geojson)

    # Find earthquakes matching the target magnitude
    matching = [
        eq for eq in earthquakes
        if abs(eq.magnitude - target_magnitude) <= tolerance
    ]

    return matching


def post_earthquake_to_twitter(earthquake, config):
    """Post an earthquake to Twitter with map image."""
    # Find Twitter channel in config
    twitter_channel = None
    for channel in config.alert_channels:
        if channel.channel_type == "twitter":
            twitter_channel = channel
            break

    if not twitter_channel:
        logger.error("No Twitter channel configured")
        return False

    if not twitter_channel.credentials:
        logger.error("Twitter channel has no credentials")
        return False

    # Convert credentials
    creds_dict = dict(twitter_channel.credentials)
    twitter_creds = TwitterCredentials(
        api_key=creds_dict["api_key"],
        api_secret=creds_dict["api_secret"],
        access_token=creds_dict["access_token"],
        access_token_secret=creds_dict["access_token_secret"],
    )

    # Get nearby POIs
    nearby_pois = get_nearby_pois(
        earthquake,
        config.points_of_interest,
        max_distance_km=100,
    )

    # Format tweet
    tweet_text = format_twitter_message(earthquake, nearby_pois)
    logger.info("Tweet text:\n%s", tweet_text)

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
            logger.info("Map image uploaded: %s", upload_result.media_id)
        else:
            logger.warning("Failed to upload map: %s", upload_result.error)
    else:
        logger.warning("Failed to generate map: %s", map_result.error)

    # Post tweet
    response = twitter_client.send_tweet(tweet_text, twitter_creds, media_ids=media_ids)

    if response.success:
        logger.info("Tweet posted successfully! ID: %s", response.tweet_id)
        return True
    else:
        logger.error("Failed to post tweet: %s", response.error)
        return False


def main():
    # Target magnitude
    target_magnitude = 3.2

    logger.info("Searching for M%.1f earthquake in the last 48 hours...", target_magnitude)

    earthquakes = find_earthquake_by_magnitude(target_magnitude, hours_back=48)

    if not earthquakes:
        logger.error("No M%.1f earthquake found in the last 48 hours", target_magnitude)
        logger.info("Trying with larger time window...")
        earthquakes = find_earthquake_by_magnitude(target_magnitude, hours_back=168)  # 1 week

    if not earthquakes:
        logger.error("No M%.1f earthquake found", target_magnitude)
        return 1

    logger.info("Found %d earthquake(s):", len(earthquakes))
    for i, eq in enumerate(earthquakes):
        logger.info("  %d. M%.1f - %s at %s", i+1, eq.magnitude, eq.place, eq.time)

    # Use the most recent one
    earthquake = earthquakes[0]
    logger.info("\nPosting the most recent: M%.1f - %s", earthquake.magnitude, earthquake.place)

    # Load config
    config_path = os.environ.get("CONFIG_PATH", "config/config-production.yaml")
    config = load_config(config_path)

    # Post to Twitter
    success = post_earthquake_to_twitter(earthquake, config)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
