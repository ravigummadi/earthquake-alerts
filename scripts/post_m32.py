#!/usr/bin/env python3
"""Standalone script to post M3.2 earthquake to Twitter."""

import os
import sys
import logging
import base64
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import requests
from requests_oauthlib import OAuth1
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bay Area bounds
BOUNDS = {
    "min_latitude": 37.3,
    "max_latitude": 38.3,
    "min_longitude": -122.5,
    "max_longitude": -121.5,
}


@dataclass
class Earthquake:
    id: str
    magnitude: float
    place: str
    latitude: float
    longitude: float
    depth_km: float
    time: datetime
    url: str


def fetch_recent_earthquakes(hours_back=48):
    """Fetch earthquakes from USGS."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_back)

    params = {
        "format": "geojson",
        "orderby": "time",
        "minlatitude": BOUNDS["min_latitude"],
        "maxlatitude": BOUNDS["max_latitude"],
        "minlongitude": BOUNDS["min_longitude"],
        "maxlongitude": BOUNDS["max_longitude"],
        "minmagnitude": "2.0",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    response = requests.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    earthquakes = []

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])

        if len(coords) < 3 or props.get("mag") is None:
            continue

        earthquakes.append(Earthquake(
            id=feature.get("id", ""),
            magnitude=float(props.get("mag", 0)),
            place=props.get("place", "Unknown"),
            latitude=coords[1],
            longitude=coords[0],
            depth_km=coords[2],
            time=datetime.fromtimestamp(props["time"] / 1000, tz=timezone.utc),
            url=props.get("url", ""),
        ))

    return earthquakes


def format_tweet(earthquake):
    """Format earthquake as a tweet."""
    lines = []

    # Magnitude prefix
    prefix = ""
    if earthquake.magnitude >= 6.0:
        prefix = "MAJOR "
    elif earthquake.magnitude >= 5.0:
        prefix = "STRONG "

    lines.append(f"{prefix}M{earthquake.magnitude:.1f} earthquake - {earthquake.place}")
    lines.append(f"Depth: {earthquake.depth_km:.0f}km")
    lines.append("https://earthquake.city/sanramon")

    if earthquake.url:
        lines.append(earthquake.url)

    return "\n".join(lines)


def generate_map_image(lat, lon, magnitude):
    """Generate a static map image using open-meteo/mapbox."""
    # Use a free static map API
    zoom = 8 if magnitude >= 5.0 else 9 if magnitude >= 4.0 else 10
    color = "ff0000" if magnitude >= 5.0 else "ff6600" if magnitude >= 4.0 else "ffcc00"

    url = (
        f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/"
        f"pin-l+{color}({lon},{lat})/{lon},{lat},{zoom}/600x400@2x"
        f"?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw"
    )

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.warning("Failed to generate map: %s", e)

    return None


def upload_media_to_twitter(image_bytes, credentials):
    """Upload image to Twitter."""
    auth = OAuth1(
        credentials["api_key"],
        client_secret=credentials["api_secret"],
        resource_owner_key=credentials["access_token"],
        resource_owner_secret=credentials["access_token_secret"],
    )

    media_data = base64.b64encode(image_bytes).decode("utf-8")

    response = requests.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        data={"media_data": media_data},
        auth=auth,
        timeout=30,
    )

    if response.status_code in (200, 201):
        return response.json().get("media_id_string")

    logger.error("Media upload failed: %s", response.text)
    return None


def post_tweet(text, credentials, media_ids=None):
    """Post a tweet."""
    auth = OAuth1(
        credentials["api_key"],
        client_secret=credentials["api_secret"],
        resource_owner_key=credentials["access_token"],
        resource_owner_secret=credentials["access_token_secret"],
    )

    payload = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}

    response = requests.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
        auth=auth,
        timeout=10,
    )

    if response.status_code in (200, 201):
        data = response.json()
        return data.get("data", {}).get("id")

    logger.error("Tweet failed: %d - %s", response.status_code, response.text)
    return None


def load_twitter_credentials():
    """Load Twitter credentials from config or environment."""
    # Try config file first
    config_path = os.environ.get("CONFIG_PATH", "config/config-production.yaml")

    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f)

        for channel in config.get("alert_channels", []):
            if channel.get("type") == "twitter":
                creds = channel.get("credentials", {})
                # Check if credentials are actual values (not placeholders)
                api_key = creds.get("api_key", "")
                if api_key and not api_key.startswith("${"):
                    return creds

    # Try environment variables
    if os.environ.get("TWITTER_API_KEY"):
        return {
            "api_key": os.environ["TWITTER_API_KEY"],
            "api_secret": os.environ["TWITTER_API_SECRET"],
            "access_token": os.environ["TWITTER_ACCESS_TOKEN"],
            "access_token_secret": os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
        }

    return None


def main():
    target_magnitude = 3.2

    logger.info("Fetching recent earthquakes from USGS...")
    earthquakes = fetch_recent_earthquakes(hours_back=48)

    # Find M3.2 earthquake
    matching = [eq for eq in earthquakes if abs(eq.magnitude - target_magnitude) < 0.05]

    if not matching:
        logger.info("No M3.2 found in 48 hours, trying 1 week...")
        earthquakes = fetch_recent_earthquakes(hours_back=168)
        matching = [eq for eq in earthquakes if abs(eq.magnitude - target_magnitude) < 0.05]

    if not matching:
        logger.error("No M%.1f earthquake found", target_magnitude)
        # Show what we did find
        logger.info("Found %d earthquakes total:", len(earthquakes))
        for eq in earthquakes[:10]:
            logger.info("  M%.1f - %s", eq.magnitude, eq.place)
        return 1

    earthquake = matching[0]
    logger.info("Found: M%.1f - %s at %s", earthquake.magnitude, earthquake.place, earthquake.time)

    # Load credentials
    credentials = load_twitter_credentials()
    if not credentials:
        logger.error("Twitter credentials not found. Set environment variables:")
        logger.error("  TWITTER_API_KEY, TWITTER_API_SECRET")
        logger.error("  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
        return 1

    # Format tweet
    tweet_text = format_tweet(earthquake)
    logger.info("Tweet:\n%s", tweet_text)

    # Generate and upload map
    media_ids = None
    map_image = generate_map_image(earthquake.latitude, earthquake.longitude, earthquake.magnitude)
    if map_image:
        media_id = upload_media_to_twitter(map_image, credentials)
        if media_id:
            media_ids = [media_id]
            logger.info("Map uploaded: %s", media_id)

    # Post tweet
    tweet_id = post_tweet(tweet_text, credentials, media_ids)
    if tweet_id:
        logger.info("Tweet posted successfully! ID: %s", tweet_id)
        logger.info("URL: https://twitter.com/quake_alerts/status/%s", tweet_id)
        return 0
    else:
        logger.error("Failed to post tweet")
        return 1


if __name__ == "__main__":
    sys.exit(main())
