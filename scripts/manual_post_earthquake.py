#!/usr/bin/env python3
"""Manual earthquake posting script.

This script allows manually posting earthquakes to Twitter/X
that may have been missed due to deduplication or other issues.

Usage:
    # List recent earthquakes
    python scripts/manual_post_earthquake.py --list

    # Post specific earthquake by ID
    python scripts/manual_post_earthquake.py --id nc75106941

    # Post earthquake by magnitude (most recent match)
    python scripts/manual_post_earthquake.py --magnitude 3.2

    # Post multiple earthquakes by index (from --list output)
    python scripts/manual_post_earthquake.py --indices 1,2,3

    # Dry run (preview without posting)
    python scripts/manual_post_earthquake.py --list --dry-run

Environment:
    CONFIG_PATH: Path to config file (default: config/config-production.yaml)
    GCP_PROJECT: GCP project ID for Secret Manager access
"""

import argparse
import os
import sys
import logging
import time
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def fetch_recent_earthquakes(hours_back: int = 48, min_magnitude: float = 2.0) -> list:
    """Fetch all recent earthquakes from USGS."""
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
        min_magnitude=min_magnitude,
        hours=hours_back,
    )

    return parse_earthquakes(geojson)


def find_earthquake_by_magnitude(
    earthquakes: list,
    target_magnitude: float,
    tolerance: float = 0.05,
) -> list:
    """Find earthquakes matching a target magnitude."""
    return [
        eq for eq in earthquakes
        if abs(eq.magnitude - target_magnitude) <= tolerance
    ]


def find_earthquake_by_id(earthquakes: list, eq_id: str):
    """Find earthquake by USGS ID."""
    for eq in earthquakes:
        if eq.id == eq_id:
            return eq
    return None


def post_earthquake_to_twitter(earthquake, config, dry_run: bool = False):
    """Post an earthquake to Twitter with map image.

    Returns:
        Tuple of (success: bool, error: str | None)
    """
    # Find Twitter channel in config
    twitter_channel = None
    for channel in config.alert_channels:
        if channel.channel_type == "twitter":
            twitter_channel = channel
            break

    if not twitter_channel:
        return False, "No Twitter channel configured"

    if not twitter_channel.credentials:
        return False, "Twitter channel has no credentials"

    # Convert credentials
    creds_dict = dict(twitter_channel.credentials)

    # Check for unresolved secrets
    for key, value in creds_dict.items():
        if isinstance(value, str) and value.startswith("${"):
            return False, f"Credential '{key}' not resolved from Secret Manager: {value}"

    try:
        twitter_creds = TwitterCredentials(
            api_key=creds_dict["api_key"],
            api_secret=creds_dict["api_secret"],
            access_token=creds_dict["access_token"],
            access_token_secret=creds_dict["access_token_secret"],
        )
    except KeyError as e:
        return False, f"Missing credential key: {e}"

    # Get nearby POIs
    nearby_pois = get_nearby_pois(
        earthquake,
        config.points_of_interest,
        max_distance_km=100,
    )

    # Format tweet
    tweet_text = format_twitter_message(earthquake, nearby_pois)
    logger.info("Tweet text (%d chars):\n%s", len(tweet_text), tweet_text)

    if dry_run:
        logger.info("DRY RUN - Would post tweet for M%.1f %s", earthquake.magnitude, earthquake.place)
        return True, None

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
            logger.warning("Failed to upload map (continuing without): %s", upload_result.error)
    else:
        logger.warning("Failed to generate map (continuing without): %s", map_result.error)

    # Post tweet
    response = twitter_client.send_tweet(tweet_text, twitter_creds, media_ids=media_ids)

    if response.success:
        logger.info("Tweet posted successfully! ID: %s", response.tweet_id)
        logger.info("URL: https://twitter.com/quake_alerts/status/%s", response.tweet_id)
        return True, None
    else:
        error_msg = f"HTTP {response.status_code}: {response.error}"
        logger.error("Failed to post tweet: %s", error_msg)
        return False, error_msg


def list_earthquakes(earthquakes: list):
    """Display list of earthquakes with indices."""
    if not earthquakes:
        logger.info("No earthquakes found in the specified time range")
        return

    logger.info("")
    logger.info("Recent earthquakes:")
    logger.info("-" * 80)
    for i, eq in enumerate(earthquakes, 1):
        pst_offset = timezone(timedelta(hours=-8))
        local_time = eq.time.astimezone(pst_offset)
        time_str = local_time.strftime("%Y-%m-%d %H:%M PST")
        logger.info("  %2d. M%.1f - %s", i, eq.magnitude, eq.place)
        logger.info("      ID: %s | Time: %s", eq.id, time_str)
    logger.info("-" * 80)
    logger.info("Use --indices 1,2,3 to post specific earthquakes")
    logger.info("Use --id <earthquake_id> to post by USGS ID")


def main():
    parser = argparse.ArgumentParser(
        description="Manually post earthquakes to Twitter/X",
        epilog="Use this script to re-trigger earthquakes that failed to post due to deduplication or errors.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List recent earthquakes with indices",
    )
    parser.add_argument(
        "--id",
        type=str,
        help="Post earthquake by USGS ID (e.g., nc75106941)",
    )
    parser.add_argument(
        "--magnitude", "-m",
        type=float,
        help="Post earthquake by magnitude (posts most recent match)",
    )
    parser.add_argument(
        "--indices", "-i",
        type=str,
        help="Post earthquakes by indices from --list output (comma-separated, e.g., 1,2,3)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Hours to look back for earthquakes (default: 48)",
    )
    parser.add_argument(
        "--min-magnitude",
        type=float,
        default=2.5,
        help="Minimum magnitude to fetch (default: 2.5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be posted without actually posting",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=2,
        help="Delay in seconds between posting multiple tweets (default: 2)",
    )
    args = parser.parse_args()

    # If no action specified, show help
    if not (args.list or args.id or args.magnitude or args.indices):
        parser.print_help()
        return 0

    # Fetch earthquakes
    logger.info("Fetching earthquakes from the last %d hours (M%.1f+)...", args.hours, args.min_magnitude)
    earthquakes = fetch_recent_earthquakes(
        hours_back=args.hours,
        min_magnitude=args.min_magnitude,
    )
    logger.info("Found %d earthquakes", len(earthquakes))

    # Handle --list
    if args.list:
        list_earthquakes(earthquakes)
        return 0

    # Load config for posting
    config_path = os.environ.get("CONFIG_PATH", "config/config-production.yaml")
    logger.info("Loading configuration from %s", config_path)
    config = load_config(config_path)

    # Collect earthquakes to post
    to_post = []

    if args.id:
        eq = find_earthquake_by_id(earthquakes, args.id)
        if eq:
            to_post.append(eq)
        else:
            logger.error("Earthquake with ID '%s' not found in last %d hours", args.id, args.hours)
            logger.info("Use --list to see available earthquakes")
            return 1

    if args.magnitude:
        matches = find_earthquake_by_magnitude(earthquakes, args.magnitude)
        if matches:
            to_post.append(matches[0])  # Most recent match
            logger.info("Found M%.1f earthquake: %s", matches[0].magnitude, matches[0].place)
        else:
            logger.error("No earthquake with magnitude ~%.1f found in last %d hours", args.magnitude, args.hours)
            return 1

    if args.indices:
        try:
            indices = [int(i.strip()) for i in args.indices.split(",")]
            for idx in indices:
                if 1 <= idx <= len(earthquakes):
                    to_post.append(earthquakes[idx - 1])
                else:
                    logger.warning("Index %d out of range (1-%d), skipping", idx, len(earthquakes))
        except ValueError:
            logger.error("Invalid indices format. Use comma-separated numbers, e.g., 1,2,3")
            return 1

    if not to_post:
        logger.error("No earthquakes selected for posting")
        return 1

    # Remove duplicates while preserving order
    seen = set()
    unique_to_post = []
    for eq in to_post:
        if eq.id not in seen:
            seen.add(eq.id)
            unique_to_post.append(eq)
    to_post = unique_to_post

    # Post earthquakes
    logger.info("")
    logger.info("=" * 60)
    logger.info("Posting %d earthquake(s) to Twitter%s",
                len(to_post),
                " (DRY RUN)" if args.dry_run else "")
    logger.info("=" * 60)

    results = []
    for i, eq in enumerate(to_post):
        logger.info("")
        logger.info("[%d/%d] Posting M%.1f - %s", i + 1, len(to_post), eq.magnitude, eq.place)

        success, error = post_earthquake_to_twitter(eq, config, dry_run=args.dry_run)
        results.append((eq, success, error))

        # Rate limit between posts
        if i < len(to_post) - 1 and not args.dry_run:
            logger.info("Waiting %d seconds before next post...", args.delay)
            time.sleep(args.delay)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Summary:")
    successes = sum(1 for _, s, _ in results if s)
    failures = sum(1 for _, s, _ in results if not s)
    logger.info("  Posted: %d", successes)
    logger.info("  Failed: %d", failures)

    if failures > 0:
        logger.info("")
        logger.info("Failed earthquakes:")
        for eq, success, error in results:
            if not success:
                logger.info("  - M%.1f %s: %s", eq.magnitude, eq.place, error)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
