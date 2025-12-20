"""Configuration Loader - Imperative Shell.

This module handles loading configuration from YAML files and
environment variables. All I/O is contained here.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel, AlertRule


logger = logging.getLogger(__name__)


@dataclass
class MonitoringRegion:
    """A geographic region to monitor for earthquakes.

    Attributes:
        name: Human-readable name
        bounds: Geographic bounding box
    """
    name: str
    bounds: BoundingBox


@dataclass
class Config:
    """Application configuration.

    Attributes:
        polling_interval_seconds: How often to check for new earthquakes
        lookback_hours: How far back to fetch earthquakes
        monitoring_regions: Regions to monitor
        alert_channels: Notification channels with their rules
        points_of_interest: Named locations for proximity alerts
        firestore_collection: Firestore collection for deduplication
        min_fetch_magnitude: Minimum magnitude to fetch from USGS
    """
    polling_interval_seconds: int = 60
    lookback_hours: int = 1
    monitoring_regions: list[MonitoringRegion] = field(default_factory=list)
    alert_channels: list[AlertChannel] = field(default_factory=list)
    points_of_interest: list[PointOfInterest] = field(default_factory=list)
    firestore_collection: str = "earthquake_alerts"
    min_fetch_magnitude: float | None = None


def _expand_env_vars(value: str) -> str:
    """Expand environment variables in a string.

    Supports ${VAR_NAME} syntax.
    """
    if not isinstance(value, str):
        return value

    if value.startswith("${") and value.endswith("}"):
        var_name = value[2:-1]
        env_value = os.environ.get(var_name)
        if env_value is None:
            logger.warning("Environment variable %s not set", var_name)
            return value
        return env_value

    return value


def _parse_bounds(data: dict[str, Any]) -> BoundingBox:
    """Parse a bounding box from config data."""
    return BoundingBox(
        min_latitude=float(data["min_latitude"]),
        max_latitude=float(data["max_latitude"]),
        min_longitude=float(data["min_longitude"]),
        max_longitude=float(data["max_longitude"]),
    )


def _parse_poi(data: dict[str, Any]) -> PointOfInterest:
    """Parse a point of interest from config data."""
    return PointOfInterest(
        name=data["name"],
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        alert_radius_km=float(data.get("alert_radius_km", 50)),
    )


def _parse_alert_rule(data: dict[str, Any], pois: list[PointOfInterest]) -> AlertRule:
    """Parse an alert rule from config data."""
    bounds = None
    if "bounds" in data:
        bounds = _parse_bounds(data["bounds"])

    # Match POIs by name
    rule_pois: list[PointOfInterest] = []
    if "points_of_interest" in data:
        poi_names = set(data["points_of_interest"])
        rule_pois = [p for p in pois if p.name in poi_names]

    return AlertRule(
        min_magnitude=float(data.get("min_magnitude", 0.0)),
        max_magnitude=data.get("max_magnitude"),
        bounds=bounds,
        points_of_interest=tuple(rule_pois),
        alert_on_tsunami=data.get("alert_on_tsunami", True),
        alert_on_felt=data.get("alert_on_felt", False),
        felt_threshold=int(data.get("felt_threshold", 10)),
    )


def _parse_channel(data: dict[str, Any], pois: list[PointOfInterest]) -> AlertChannel:
    """Parse an alert channel from config data."""
    webhook_url = _expand_env_vars(data["webhook_url"])
    rules_data = data.get("rules", {})

    return AlertChannel(
        name=data["name"],
        channel_type=data.get("type", "slack"),
        webhook_url=webhook_url,
        rules=_parse_alert_rule(rules_data, pois),
    )


def _parse_region(data: dict[str, Any]) -> MonitoringRegion:
    """Parse a monitoring region from config data."""
    return MonitoringRegion(
        name=data["name"],
        bounds=_parse_bounds(data["bounds"]),
    )


def load_config_from_dict(data: dict[str, Any]) -> Config:
    """Load configuration from a dictionary.

    This is a pure-ish function (only env var expansion has side effects).

    Args:
        data: Configuration dictionary

    Returns:
        Parsed Config object
    """
    # Parse POIs first (channels may reference them)
    pois = [
        _parse_poi(p)
        for p in data.get("points_of_interest", [])
    ]

    # Parse regions
    regions = [
        _parse_region(r)
        for r in data.get("monitoring_regions", [])
    ]

    # Parse channels
    channels = [
        _parse_channel(c, pois)
        for c in data.get("alert_channels", [])
    ]

    return Config(
        polling_interval_seconds=int(data.get("polling_interval_seconds", 60)),
        lookback_hours=int(data.get("lookback_hours", 1)),
        monitoring_regions=regions,
        alert_channels=channels,
        points_of_interest=pois,
        firestore_collection=data.get("firestore_collection", "earthquake_alerts"),
        min_fetch_magnitude=data.get("min_fetch_magnitude"),
    )


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from a YAML file.

    This method performs file I/O.

    Args:
        config_path: Path to YAML config file.
                    If None, uses CONFIG_PATH env var or default.

    Returns:
        Parsed Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    path = Path(config_path)

    logger.info("Loading configuration from %s", path)

    if not path.exists():
        logger.warning("Config file not found: %s, using defaults", path)
        return Config()

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        logger.warning("Config file is empty, using defaults")
        return Config()

    config = load_config_from_dict(data)

    logger.info(
        "Loaded config: %d regions, %d channels, %d POIs",
        len(config.monitoring_regions),
        len(config.alert_channels),
        len(config.points_of_interest),
    )

    return config


def load_config_from_env() -> Config:
    """Load minimal configuration from environment variables.

    Useful for simple deployments without a YAML file.

    Environment variables:
        SLACK_WEBHOOK_URL: Webhook URL for alerts
        MONITORING_BOUNDS: Comma-separated bounds (min_lat,max_lat,min_lon,max_lon)
        MIN_MAGNITUDE: Minimum magnitude to alert on
        LOOKBACK_HOURS: How far back to check

    Returns:
        Config object from environment
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set")
        return Config()

    bounds = None
    bounds_str = os.environ.get("MONITORING_BOUNDS")
    if bounds_str:
        parts = [float(p.strip()) for p in bounds_str.split(",")]
        if len(parts) == 4:
            bounds = BoundingBox(
                min_latitude=parts[0],
                max_latitude=parts[1],
                min_longitude=parts[2],
                max_longitude=parts[3],
            )

    min_magnitude = float(os.environ.get("MIN_MAGNITUDE", "2.5"))
    lookback_hours = int(os.environ.get("LOOKBACK_HOURS", "1"))

    rule = AlertRule(
        min_magnitude=min_magnitude,
        bounds=bounds,
    )

    channel = AlertChannel(
        name="default",
        channel_type="slack",
        webhook_url=webhook_url,
        rules=rule,
    )

    regions = []
    if bounds:
        regions.append(MonitoringRegion(name="default", bounds=bounds))

    return Config(
        lookback_hours=lookback_hours,
        monitoring_regions=regions,
        alert_channels=[channel],
        min_fetch_magnitude=min_magnitude,
    )
