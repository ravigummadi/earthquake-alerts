"""Earthquake API - FastAPI service for earthquake.city.

Consolidated API endpoints deployed as a single Cloud Run service.
Reads locale configurations from Firestore with fallback to hardcoded defaults.
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import FastAPI, Query, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ===== Data Models =====

@dataclass
class BoundingBox:
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float


# Pydantic models for admin endpoints
class BoundsCreate(BaseModel):
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float


class CenterCreate(BaseModel):
    lat: float
    lng: float


class LocaleCreate(BaseModel):
    slug: str
    name: str
    display_name: str
    bounds: BoundsCreate
    center: CenterCreate
    min_magnitude: float = 2.5
    is_active: bool = True
    is_featured: bool = True
    sort_order: int = 0


class LocaleUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    bounds: BoundsCreate | None = None
    center: CenterCreate | None = None
    min_magnitude: float | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None


# ===== Firestore Locale Client =====

# Firestore configuration
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "earthquake-alerts")
LOCALES_COLLECTION = "locales"
CACHE_TTL_SECONDS = 300  # 5 minutes

# Admin API key (set in Cloud Run environment)
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")

# Locale cache
_locale_cache: dict[str, dict[str, Any]] = {}
_cache_timestamp: float = 0
_firestore_client = None


def _get_firestore_client():
    """Get or create Firestore client."""
    global _firestore_client
    if _firestore_client is None:
        try:
            from google.cloud import firestore
            _firestore_client = firestore.Client(database=FIRESTORE_DATABASE)
            logger.info("Firestore client initialized for database: %s", FIRESTORE_DATABASE)
        except Exception as e:
            logger.warning("Failed to initialize Firestore client: %s", e)
            return None
    return _firestore_client


def _is_cache_valid() -> bool:
    """Check if locale cache is still valid."""
    if not _locale_cache:
        return False
    elapsed = time.time() - _cache_timestamp
    return elapsed < CACHE_TTL_SECONDS


def _refresh_locale_cache() -> None:
    """Refresh locale cache from Firestore."""
    global _locale_cache, _cache_timestamp

    client = _get_firestore_client()
    if client is None:
        logger.warning("No Firestore client, using fallback locales")
        return

    try:
        docs = client.collection(LOCALES_COLLECTION).stream()
        new_cache = {}

        for doc in docs:
            data = doc.to_dict()
            if data and data.get("is_active", True):
                slug = data.get("slug", doc.id)
                bounds_data = data.get("bounds", {})
                new_cache[slug] = {
                    "name": data.get("name", slug),
                    "display_name": data.get("display_name", slug),
                    "bounds": BoundingBox(
                        min_latitude=bounds_data.get("min_latitude", 0),
                        max_latitude=bounds_data.get("max_latitude", 0),
                        min_longitude=bounds_data.get("min_longitude", 0),
                        max_longitude=bounds_data.get("max_longitude", 0),
                    ),
                    "center": data.get("center", {"lat": 0, "lng": 0}),
                    "min_magnitude": data.get("min_magnitude", 2.5),
                    "is_featured": data.get("is_featured", True),
                    "sort_order": data.get("sort_order", 0),
                }

        if new_cache:
            _locale_cache.clear()
            _locale_cache.update(new_cache)
            _cache_timestamp = time.time()
            logger.info("Loaded %d locales from Firestore", len(new_cache))
        else:
            logger.warning("No locales found in Firestore, keeping fallback")

    except Exception as e:
        logger.error("Failed to refresh locale cache: %s", e)
        # Keep existing cache or use fallback


def _invalidate_cache() -> None:
    """Invalidate the locale cache."""
    global _cache_timestamp
    _cache_timestamp = 0


# ===== Fallback Locale (used when Firestore is unavailable) =====

def _load_fallback_locale() -> dict[str, dict[str, Any]]:
    """Load fallback locale from shared JSON file."""
    import json
    from pathlib import Path

    # Try relative path from api/ directory, then absolute
    paths = [
        Path(__file__).parent.parent / "shared" / "fallback-locale.json",
        Path("/app/shared/fallback-locale.json"),  # Cloud Run container path
    ]

    for path in paths:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return {
                    data["slug"]: {
                        "name": data["name"],
                        "display_name": data["display_name"],
                        "bounds": BoundingBox(
                            min_latitude=data["bounds"]["min_latitude"],
                            max_latitude=data["bounds"]["max_latitude"],
                            min_longitude=data["bounds"]["min_longitude"],
                            max_longitude=data["bounds"]["max_longitude"],
                        ),
                        "center": data["center"],
                        "min_magnitude": data["min_magnitude"],
                        "is_featured": True,
                        "sort_order": 1,
                    }
                }

    # Hardcoded ultimate fallback if file not found
    logger.warning("Fallback locale file not found, using hardcoded default")
    return {
        "sanramon": {
            "name": "San Ramon",
            "display_name": "San Ramon, CA",
            "bounds": BoundingBox(37.3, 38.3, -122.5, -121.5),
            "center": {"lat": 37.78, "lng": -121.98},
            "min_magnitude": 2.5,
            "is_featured": True,
            "sort_order": 1,
        }
    }

FALLBACK_LOCALES = _load_fallback_locale()

USGS_API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


# ===== Helper Functions =====

def _get_locales() -> dict[str, dict[str, Any]]:
    """Get locales from cache or Firestore, with fallback."""
    if not _is_cache_valid():
        _refresh_locale_cache()

    if _locale_cache:
        return _locale_cache

    return FALLBACK_LOCALES


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
    locales = _get_locales()

    if locale not in locales:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Unknown locale: {locale}", "available": list(locales.keys())},
        )
    return locales[locale]


def _build_region_response(locale: str, config: dict[str, Any]) -> dict[str, Any]:
    """Build region info for response."""
    return {
        "slug": locale,
        "name": config["name"],
        "display_name": config["display_name"],
        "bounds": _bounds_to_dict(config["bounds"]),
        "center": config["center"],
    }


def _verify_admin_key(x_admin_key: str | None) -> None:
    """Verify admin API key."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin API key not configured")

    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


# ===== Public Endpoints =====

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
    except requests.RequestException:
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
    except requests.RequestException:
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
    """List all available locales (featured ones only)."""
    locales = _get_locales()

    result = [
        {
            "slug": slug,
            "name": config["name"],
            "display_name": config["display_name"],
            "bounds": _bounds_to_dict(config["bounds"]),
            "center": config["center"],
            "min_magnitude": config["min_magnitude"],
        }
        for slug, config in locales.items()
        if config.get("is_featured", True)
    ]

    # Sort by sort_order, then name
    result.sort(key=lambda x: (locales.get(x["slug"], {}).get("sort_order", 0), x["name"]))

    return {"locales": result}


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}


# ===== Admin Endpoints =====

@app.get("/api-admin/locales")
async def admin_list_locales(x_admin_key: str | None = Header(default=None)):
    """List all locales (including inactive) for admin."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        docs = client.collection(LOCALES_COLLECTION).stream()
        locales = []

        for doc in docs:
            data = doc.to_dict()
            if data:
                locales.append({
                    "slug": data.get("slug", doc.id),
                    "name": data.get("name"),
                    "display_name": data.get("display_name"),
                    "bounds": data.get("bounds"),
                    "center": data.get("center"),
                    "min_magnitude": data.get("min_magnitude", 2.5),
                    "is_active": data.get("is_active", True),
                    "is_featured": data.get("is_featured", True),
                    "sort_order": data.get("sort_order", 0),
                    "created_at": str(data.get("created_at")) if data.get("created_at") else None,
                    "updated_at": str(data.get("updated_at")) if data.get("updated_at") else None,
                })

        locales.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
        return {"locales": locales}

    except Exception as e:
        logger.error("Failed to fetch locales for admin: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api-admin/locales/{slug}")
async def admin_get_locale(slug: str, x_admin_key: str | None = Header(default=None)):
    """Get a single locale by slug."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        doc = client.collection(LOCALES_COLLECTION).document(slug).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Locale '{slug}' not found")

        data = doc.to_dict()
        return {
            "slug": data.get("slug", slug),
            "name": data.get("name"),
            "display_name": data.get("display_name"),
            "bounds": data.get("bounds"),
            "center": data.get("center"),
            "min_magnitude": data.get("min_magnitude", 2.5),
            "is_active": data.get("is_active", True),
            "is_featured": data.get("is_featured", True),
            "sort_order": data.get("sort_order", 0),
            "created_at": str(data.get("created_at")) if data.get("created_at") else None,
            "updated_at": str(data.get("updated_at")) if data.get("updated_at") else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch locale %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api-admin/locales")
async def admin_create_locale(locale: LocaleCreate, x_admin_key: str | None = Header(default=None)):
    """Create a new locale."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        doc_ref = client.collection(LOCALES_COLLECTION).document(locale.slug)

        if doc_ref.get().exists:
            raise HTTPException(status_code=409, detail=f"Locale '{locale.slug}' already exists")

        now = datetime.now(timezone.utc)
        doc_ref.set({
            "slug": locale.slug,
            "name": locale.name,
            "display_name": locale.display_name,
            "bounds": locale.bounds.model_dump(),
            "center": locale.center.model_dump(),
            "min_magnitude": locale.min_magnitude,
            "is_active": locale.is_active,
            "is_featured": locale.is_featured,
            "sort_order": locale.sort_order,
            "created_at": now,
            "updated_at": now,
        })

        _invalidate_cache()
        return {"message": f"Locale '{locale.slug}' created successfully", "slug": locale.slug}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create locale %s: %s", locale.slug, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api-admin/locales/{slug}")
async def admin_update_locale(
    slug: str,
    updates: LocaleUpdate,
    x_admin_key: str | None = Header(default=None),
):
    """Update an existing locale."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        doc_ref = client.collection(LOCALES_COLLECTION).document(slug)

        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Locale '{slug}' not found")

        update_data: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

        if updates.name is not None:
            update_data["name"] = updates.name
        if updates.display_name is not None:
            update_data["display_name"] = updates.display_name
        if updates.bounds is not None:
            update_data["bounds"] = updates.bounds.model_dump()
        if updates.center is not None:
            update_data["center"] = updates.center.model_dump()
        if updates.min_magnitude is not None:
            update_data["min_magnitude"] = updates.min_magnitude
        if updates.is_active is not None:
            update_data["is_active"] = updates.is_active
        if updates.is_featured is not None:
            update_data["is_featured"] = updates.is_featured
        if updates.sort_order is not None:
            update_data["sort_order"] = updates.sort_order

        doc_ref.update(update_data)
        _invalidate_cache()

        return {"message": f"Locale '{slug}' updated successfully", "slug": slug}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update locale %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api-admin/locales/{slug}")
async def admin_delete_locale(
    slug: str,
    hard: bool = Query(default=False),
    x_admin_key: str | None = Header(default=None),
):
    """Delete a locale (soft delete by default)."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        doc_ref = client.collection(LOCALES_COLLECTION).document(slug)

        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Locale '{slug}' not found")

        if hard:
            doc_ref.delete()
            action = "deleted permanently"
        else:
            doc_ref.update({
                "is_active": False,
                "updated_at": datetime.now(timezone.utc),
            })
            action = "deactivated"

        _invalidate_cache()
        return {"message": f"Locale '{slug}' {action}", "slug": slug}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete locale %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api-admin/locales/{slug}/restore")
async def admin_restore_locale(slug: str, x_admin_key: str | None = Header(default=None)):
    """Restore a soft-deleted locale."""
    _verify_admin_key(x_admin_key)

    client = _get_firestore_client()
    if client is None:
        raise HTTPException(status_code=500, detail="Firestore not available")

    try:
        doc_ref = client.collection(LOCALES_COLLECTION).document(slug)

        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Locale '{slug}' not found")

        doc_ref.update({
            "is_active": True,
            "updated_at": datetime.now(timezone.utc),
        })

        _invalidate_cache()
        return {"message": f"Locale '{slug}' restored", "slug": slug}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to restore locale %s: %s", slug, e)
        raise HTTPException(status_code=500, detail=str(e))
