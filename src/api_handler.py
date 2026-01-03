"""Web API Handler - Serves earthquake data for earthquake.city.

This module provides HTTP endpoints for the web frontend.
Part of the imperative shell - handles HTTP I/O.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Request, Response

from src.core.earthquake import Earthquake, parse_earthquakes
from src.core.geo import BoundingBox
from src.shell.usgs_client import USGSClient, USGSQueryParams

logger = logging.getLogger(__name__)

# Locale configurations - maps URL slugs to regions
# Bounds must match api/main.py and config/config-production.yaml
LOCALES: dict[str, dict[str, Any]] = {
    "sanramon": {
        "name": "San Ramon",
        "display_name": "San Ramon, CA",
        "bounds": BoundingBox(
            min_latitude=37.3,
            max_latitude=38.3,
            min_longitude=-122.5,
            max_longitude=-121.5,
        ),
        "center": {"lat": 37.78, "lng": -121.98},
        "min_magnitude": 2.5,
    },
    "bayarea": {
        "name": "Bay Area",
        "display_name": "San Francisco Bay Area",
        "bounds": BoundingBox(
            min_latitude=37.0,
            max_latitude=38.5,
            min_longitude=-123.0,
            max_longitude=-121.5,
        ),
        "center": {"lat": 37.77, "lng": -122.42},
        "min_magnitude": 2.5,
    },
    "la": {
        "name": "Los Angeles",
        "display_name": "Los Angeles, CA",
        "bounds": BoundingBox(
            min_latitude=33.5,
            max_latitude=34.8,
            min_longitude=-119.0,
            max_longitude=-117.0,
        ),
        "center": {"lat": 34.05, "lng": -118.24},
        "min_magnitude": 2.5,
    },
}

# CORS allowed origins
ALLOWED_ORIGINS = [
    "https://earthquake.city",
    "http://localhost:3000",
    "http://localhost:3001",
]


def _cors_headers(origin: str | None) -> dict[str, str]:
    """Generate CORS headers for the response."""
    headers = {
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }
    if origin and (origin in ALLOWED_ORIGINS or origin.endswith(".earthquake.city")):
        headers["Access-Control-Allow-Origin"] = origin
    else:
        headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
    return headers


def _json_response(
    data: dict[str, Any],
    status: int = 200,
    origin: str | None = None,
) -> Response:
    """Create a JSON response with CORS headers."""
    response = Response(
        json.dumps(data, default=str),
        status=status,
        mimetype="application/json",
    )
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value
    return response


def _earthquake_to_dict(eq: Earthquake) -> dict[str, Any]:
    """Convert Earthquake dataclass to JSON-serializable dict."""
    return {
        "id": eq.id,
        "magnitude": eq.magnitude,
        "place": eq.place,
        "time": eq.time.isoformat(),
        "latitude": eq.latitude,
        "longitude": eq.longitude,
        "depth_km": eq.depth_km,
        "url": eq.url,
        "felt": eq.felt,
        "alert": eq.alert,
        "tsunami": eq.tsunami,
        "mag_type": eq.mag_type,
        "has_shakemap": eq.has_shakemap,
    }


def _bounds_to_dict(bounds: BoundingBox) -> dict[str, float]:
    """Convert BoundingBox to dict."""
    return {
        "min_latitude": bounds.min_latitude,
        "max_latitude": bounds.max_latitude,
        "min_longitude": bounds.min_longitude,
        "max_longitude": bounds.max_longitude,
    }


def get_latest_earthquake(request: Request) -> Response:
    """API endpoint: Get the latest earthquake for a locale.

    Query params:
        locale: URL slug (e.g., "sanramon", "bayarea", "la")

    Returns:
        JSON with region info and latest earthquake
    """
    origin = request.headers.get("Origin")

    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = Response("", status=204)
        for key, value in _cors_headers(origin).items():
            response.headers[key] = value
        return response

    # Get locale from query params
    locale = request.args.get("locale", "sanramon")

    if locale not in LOCALES:
        return _json_response(
            {"error": f"Unknown locale: {locale}", "available": list(LOCALES.keys())},
            status=404,
            origin=origin,
        )

    locale_config = LOCALES[locale]
    bounds = locale_config["bounds"]
    min_magnitude = locale_config["min_magnitude"]

    # Fetch earthquakes from USGS (look back 30 days for latest)
    client = USGSClient()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)

    query = USGSQueryParams(
        bounds=bounds,
        min_magnitude=min_magnitude,
        start_time=start,
        end_time=now,
        limit=1,
    )

    try:
        geojson = client.fetch_earthquakes(query)
        earthquakes = parse_earthquakes(geojson)
    except Exception as e:
        logger.exception("Failed to fetch earthquakes from USGS")
        return _json_response(
            {"error": "Failed to fetch earthquake data"},
            status=502,
            origin=origin,
        )

    # Build response
    response_data: dict[str, Any] = {
        "region": {
            "slug": locale,
            "name": locale_config["name"],
            "display_name": locale_config["display_name"],
            "bounds": _bounds_to_dict(bounds),
            "center": locale_config["center"],
        },
        "min_magnitude_filter": min_magnitude,
        "latest_earthquake": None,
        "fetched_at": now.isoformat(),
    }

    if earthquakes:
        response_data["latest_earthquake"] = _earthquake_to_dict(earthquakes[0])

    return _json_response(response_data, origin=origin)


def get_recent_earthquakes(request: Request) -> Response:
    """API endpoint: Get recent earthquakes for a locale.

    Query params:
        locale: URL slug (e.g., "sanramon", "bayarea", "la")
        limit: Number of earthquakes to return (default 10, max 50)

    Returns:
        JSON with region info and list of recent earthquakes
    """
    origin = request.headers.get("Origin")

    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = Response("", status=204)
        for key, value in _cors_headers(origin).items():
            response.headers[key] = value
        return response

    # Get locale from query params
    locale = request.args.get("locale", "sanramon")
    limit = min(int(request.args.get("limit", "10")), 50)

    if locale not in LOCALES:
        return _json_response(
            {"error": f"Unknown locale: {locale}", "available": list(LOCALES.keys())},
            status=404,
            origin=origin,
        )

    locale_config = LOCALES[locale]
    bounds = locale_config["bounds"]
    min_magnitude = locale_config["min_magnitude"]

    # Fetch earthquakes from USGS (look back 30 days)
    client = USGSClient()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)

    query = USGSQueryParams(
        bounds=bounds,
        min_magnitude=min_magnitude,
        start_time=start,
        end_time=now,
        limit=limit,
    )

    try:
        geojson = client.fetch_earthquakes(query)
        earthquakes = parse_earthquakes(geojson)
    except Exception as e:
        logger.exception("Failed to fetch earthquakes from USGS")
        return _json_response(
            {"error": "Failed to fetch earthquake data"},
            status=502,
            origin=origin,
        )

    # Build response
    response_data: dict[str, Any] = {
        "region": {
            "slug": locale,
            "name": locale_config["name"],
            "display_name": locale_config["display_name"],
            "bounds": _bounds_to_dict(bounds),
            "center": locale_config["center"],
        },
        "min_magnitude_filter": min_magnitude,
        "earthquakes": [_earthquake_to_dict(eq) for eq in earthquakes],
        "count": len(earthquakes),
        "fetched_at": now.isoformat(),
    }

    return _json_response(response_data, origin=origin)


def get_locales(request: Request) -> Response:
    """API endpoint: List all available locales.

    Returns:
        JSON with list of available locales (full config for frontend)
    """
    origin = request.headers.get("Origin")

    if request.method == "OPTIONS":
        response = Response("", status=204)
        for key, value in _cors_headers(origin).items():
            response.headers[key] = value
        return response

    locales = [
        {
            "slug": slug,
            "name": config["name"],
            "display_name": config["display_name"],
            "bounds": _bounds_to_dict(config["bounds"]),
            "center": config["center"],
            "min_magnitude": config["min_magnitude"],
        }
        for slug, config in LOCALES.items()
    ]

    return _json_response({"locales": locales}, origin=origin)
