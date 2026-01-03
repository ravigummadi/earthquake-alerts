"""Earthquake API - FastAPI service for earthquake.city.

Consolidated API endpoints deployed as a single Cloud Run service.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Earthquake API",
    description="API for earthquake.city - serves earthquake data from USGS",
    version="1.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://earthquake.city",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_origin_regex=r"https://.*\.earthquake\.city",
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# Data models
@dataclass
class BoundingBox:
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float


# Locale configurations
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

USGS_API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def _bounds_to_dict(bounds: BoundingBox) -> dict[str, float]:
    """Convert BoundingBox to dict."""
    return {
        "min_latitude": bounds.min_latitude,
        "max_latitude": bounds.max_latitude,
        "min_longitude": bounds.min_longitude,
        "max_longitude": bounds.max_longitude,
    }


def _earthquake_to_dict(feature: dict[str, Any]) -> dict[str, Any]:
    """Convert USGS GeoJSON feature to API response format."""
    props = feature["properties"]
    coords = feature["geometry"]["coordinates"]

    # Convert Unix timestamp (ms) to ISO format
    time_ms = props.get("time")
    time_iso = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc).isoformat() if time_ms else None

    return {
        "id": feature["id"],
        "magnitude": props.get("mag"),
        "place": props.get("place"),
        "time": time_iso,
        "latitude": coords[1],
        "longitude": coords[0],
        "depth_km": coords[2],
        "url": props.get("url"),
        "felt": props.get("felt"),
        "alert": props.get("alert"),
        "tsunami": bool(props.get("tsunami")),
        "mag_type": props.get("magType"),
        "has_shakemap": "shakemap" in (props.get("types") or ""),
    }


def _fetch_earthquakes(
    bounds: BoundingBox,
    min_magnitude: float,
    limit: int,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Fetch earthquakes from USGS API."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)

    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minlatitude": bounds.min_latitude,
        "maxlatitude": bounds.max_latitude,
        "minlongitude": bounds.min_longitude,
        "maxlongitude": bounds.max_longitude,
        "minmagnitude": min_magnitude,
        "limit": limit,
        "orderby": "time",
    }

    response = requests.get(USGS_API_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return [_earthquake_to_dict(f) for f in data.get("features", [])]


def _get_locale_config(locale: str) -> dict[str, Any]:
    """Get locale config or raise 404."""
    if locale not in LOCALES:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Unknown locale: {locale}", "available": list(LOCALES.keys())},
        )
    return LOCALES[locale]


def _build_region_response(locale: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build region info for response."""
    return {
        "slug": locale,
        "name": config["name"],
        "display_name": config["display_name"],
        "bounds": _bounds_to_dict(config["bounds"]),
        "center": config["center"],
    }


@app.get("/api-latest-earthquake")
async def get_latest_earthquake(locale: str = Query(default="sanramon")):
    """Get the latest earthquake for a locale."""
    config = _get_locale_config(locale)

    try:
        earthquakes = _fetch_earthquakes(
            bounds=config["bounds"],
            min_magnitude=config["min_magnitude"],
            limit=1,
        )
    except requests.RequestException as e:
        logger.exception("Failed to fetch from USGS")
        raise HTTPException(status_code=502, detail="Failed to fetch earthquake data")

    return {
        "region": _build_region_response(locale, config),
        "min_magnitude_filter": config["min_magnitude"],
        "latest_earthquake": earthquakes[0] if earthquakes else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api-recent-earthquakes")
async def get_recent_earthquakes(
    locale: str = Query(default="sanramon"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get recent earthquakes for a locale."""
    config = _get_locale_config(locale)

    try:
        earthquakes = _fetch_earthquakes(
            bounds=config["bounds"],
            min_magnitude=config["min_magnitude"],
            limit=limit,
        )
    except requests.RequestException as e:
        logger.exception("Failed to fetch from USGS")
        raise HTTPException(status_code=502, detail="Failed to fetch earthquake data")

    return {
        "region": _build_region_response(locale, config),
        "min_magnitude_filter": config["min_magnitude"],
        "earthquakes": earthquakes,
        "count": len(earthquakes),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api-locales")
async def get_locales():
    """List all available locales."""
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
    return {"locales": locales}


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}
