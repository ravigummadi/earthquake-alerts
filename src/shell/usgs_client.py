"""USGS API Client - Imperative Shell.

This module handles HTTP communication with the USGS Earthquake API.
All I/O is contained here; business logic is in the core module.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from src.core.geo import BoundingBox


logger = logging.getLogger(__name__)


# USGS FDSN Event Web Service base URL
USGS_API_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30


@dataclass
class USGSQueryParams:
    """Parameters for USGS API query.

    Attributes:
        bounds: Geographic bounding box (optional)
        min_magnitude: Minimum magnitude to fetch
        start_time: Fetch earthquakes after this time
        end_time: Fetch earthquakes before this time
        limit: Maximum number of results
    """
    bounds: BoundingBox | None = None
    min_magnitude: float | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 100


class USGSClient:
    """Client for fetching earthquake data from USGS API.

    This is part of the imperative shell - it handles HTTP I/O.
    """

    def __init__(
        self,
        base_url: str = USGS_API_BASE,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize USGS client.

        Args:
            base_url: USGS API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout

    def _build_params(self, query: USGSQueryParams) -> dict[str, str]:
        """Build query parameters for USGS API request.

        Args:
            query: Query parameters

        Returns:
            Dict of URL query parameters
        """
        params: dict[str, str] = {
            "format": "geojson",
            "orderby": "time",
        }

        if query.bounds is not None:
            params["minlatitude"] = str(query.bounds.min_latitude)
            params["maxlatitude"] = str(query.bounds.max_latitude)
            params["minlongitude"] = str(query.bounds.min_longitude)
            params["maxlongitude"] = str(query.bounds.max_longitude)

        if query.min_magnitude is not None:
            params["minmagnitude"] = str(query.min_magnitude)

        if query.start_time is not None:
            params["starttime"] = query.start_time.strftime("%Y-%m-%dT%H:%M:%S")

        if query.end_time is not None:
            params["endtime"] = query.end_time.strftime("%Y-%m-%dT%H:%M:%S")

        if query.limit is not None:
            params["limit"] = str(query.limit)

        return params

    def fetch_earthquakes(self, query: USGSQueryParams) -> dict[str, Any]:
        """Fetch earthquake data from USGS API.

        This method performs HTTP I/O.

        Args:
            query: Query parameters

        Returns:
            Raw GeoJSON response from USGS

        Raises:
            requests.RequestException: If the request fails
        """
        params = self._build_params(query)

        logger.info(
            "Fetching earthquakes from USGS",
            extra={"params": params},
        )

        response = requests.get(
            self.base_url,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        count = data.get("metadata", {}).get("count", 0)

        logger.info(
            "Fetched %d earthquakes from USGS",
            count,
        )

        return data

    def fetch_recent(
        self,
        bounds: BoundingBox | None = None,
        min_magnitude: float | None = None,
        hours: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Convenience method to fetch recent earthquakes.

        Args:
            bounds: Geographic bounds to filter by
            min_magnitude: Minimum magnitude
            hours: How many hours back to fetch
            limit: Maximum results

        Returns:
            Raw GeoJSON response
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        query = USGSQueryParams(
            bounds=bounds,
            min_magnitude=min_magnitude,
            start_time=start,
            end_time=now,
            limit=limit,
        )

        return self.fetch_earthquakes(query)
