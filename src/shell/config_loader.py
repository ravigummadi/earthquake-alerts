"""Configuration Loader - Imperative Shell.

This module handles loading configuration from YAML files and
environment variables. All I/O is contained here.

Models (Config, MonitoringRegion) are defined in src/core/config.py
to avoid information leakage between layers.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel, AlertRule
from src.core.config import Config, MonitoringRegion
from src.shell.secret_manager_client import SecretManagerClient, SecretManagerConfig


logger = logging.getLogger(__name__)


def _get_secret_manager_client() -> Optional[SecretManagerClient]:
    """Get or create a Secret Manager client.

    Returns None if GCP_PROJECT is not set (e.g., local development).
    """
    project_id = os.environ.get("GCP_PROJECT")
    if not project_id:
        # Try to get from gcloud config
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                project_id = result.stdout.strip()
        except Exception:
            pass

    if project_id:
        return SecretManagerClient(SecretManagerConfig(project_id=project_id))
    return None


def _resolve_value(value: str, secret_client: Optional[SecretManagerClient] = None) -> str:
    """Resolve a value that may contain secret or env var placeholders.

    Delegates to SecretManagerClient.resolve() which handles the complexity
    of parsing placeholder syntax (pulling complexity down).

    Args:
        value: Value to resolve (may contain ${...} placeholders)
        secret_client: Client for resolving secrets

    Returns:
        Resolved value
    """
    if not isinstance(value, str):
        return value

    if secret_client:
        return secret_client.resolve(value)

    # No secret client - only handle env vars
    if value.startswith("${") and value.endswith("}"):
        var_spec = value[2:-1]
        if not var_spec.startswith("secret:"):
            env_value = os.environ.get(var_spec)
            if env_value:
                return env_value
            logger.warning("Environment variable %s not set", var_spec)

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


def _parse_channel(
    data: dict[str, Any],
    pois: list[PointOfInterest],
    secret_client: Optional[SecretManagerClient] = None,
) -> AlertChannel:
    """Parse an alert channel from config data.

    Supports:
    - Slack channels: use webhook_url
    - Twitter channels: use credentials dict with api_key, api_secret,
                       access_token, access_token_secret
    - WhatsApp channels: use credentials dict with account_sid, auth_token,
                        from_number, and to_numbers list
    """
    channel_type = data.get("type", "slack")
    rules_data = data.get("rules", {})

    # Parse webhook_url (used by Slack, optional for others)
    webhook_url = ""
    if "webhook_url" in data:
        webhook_url = _resolve_value(data["webhook_url"], secret_client)

    # Parse credentials (used by Twitter, WhatsApp, and other OAuth channels)
    credentials = None
    if "credentials" in data:
        creds_data = data["credentials"]
        resolved_creds = {}
        for key, value in creds_data.items():
            if isinstance(value, list):
                # Handle lists (e.g., to_numbers for WhatsApp)
                resolved_creds[key] = [
                    _resolve_value(v, secret_client) for v in value
                ]
            else:
                resolved_creds[key] = _resolve_value(value, secret_client)
        # Convert to tuple of tuples for frozen dataclass compatibility
        # Lists are converted to tuples
        credentials = tuple(
            (k, tuple(v) if isinstance(v, list) else v)
            for k, v in sorted(resolved_creds.items())
        )

    return AlertChannel(
        name=data["name"],
        channel_type=channel_type,
        webhook_url=webhook_url,
        rules=_parse_alert_rule(rules_data, pois),
        credentials=credentials,
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
    # Get Secret Manager client for secret expansion
    secret_client = _get_secret_manager_client()

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

    # Parse channels (will use secret_client for webhook URLs)
    channels = [
        _parse_channel(c, pois, secret_client)
        for c in data.get("alert_channels", [])
    ]

    return Config(
        polling_interval_seconds=int(data.get("polling_interval_seconds", 60)),
        lookback_hours=int(data.get("lookback_hours", 1)),
        monitoring_regions=regions,
        alert_channels=channels,
        points_of_interest=pois,
        firestore_database=data.get("firestore_database"),
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
        SLACK_WEBHOOK_URL: Webhook URL for alerts (or use Secret Manager)
        SLACK_WEBHOOK_SECRET: Secret name in Secret Manager (alternative to SLACK_WEBHOOK_URL)
        MONITORING_BOUNDS: Comma-separated bounds (min_lat,max_lat,min_lon,max_lon)
        MIN_MAGNITUDE: Minimum magnitude to alert on
        LOOKBACK_HOURS: How far back to check

    Returns:
        Config object from environment
    """
    # Try to get webhook URL from Secret Manager first, then env var
    secret_client = _get_secret_manager_client()
    webhook_url = None

    # Check if user specified a secret name
    secret_name = os.environ.get("SLACK_WEBHOOK_SECRET", "slack-webhook-url")
    if secret_client:
        webhook_url = secret_client.get_secret(secret_name)
        if webhook_url:
            logger.info("Using Slack webhook from Secret Manager")

    # Fall back to environment variable
    if not webhook_url:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set and no secret found")
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

    firestore_database = os.environ.get("FIRESTORE_DATABASE")

    return Config(
        lookback_hours=lookback_hours,
        monitoring_regions=regions,
        alert_channels=[channel],
        min_fetch_magnitude=min_magnitude,
        firestore_database=firestore_database,
    )
