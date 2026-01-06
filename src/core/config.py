"""Configuration models - Pure data structures.

These are domain models for configuration. The actual loading
(I/O) is handled by the shell layer.
"""

from dataclasses import dataclass, field

from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel


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
class RateLimitConfig:
    """Rate limiting configuration for alerts.

    Attributes:
        max_alerts_per_run: Maximum total alerts per monitoring cycle (0 = unlimited)
        max_alerts_per_channel: Maximum alerts per channel per cycle (0 = unlimited)
        fail_on_limit_exceeded: If True, raise error when limit exceeded; else warn
    """
    max_alerts_per_run: int = 10
    max_alerts_per_channel: int = 5
    fail_on_limit_exceeded: bool = False


@dataclass
class Config:
    """Application configuration.

    This is a pure data structure - no I/O or side effects.

    Attributes:
        polling_interval_seconds: How often to check for new earthquakes
        lookback_hours: How far back to fetch earthquakes
        monitoring_regions: Regions to monitor
        alert_channels: Notification channels with their rules
        points_of_interest: Named locations for proximity alerts
        firestore_database: Firestore database name (None for default)
        firestore_collection: Firestore collection for deduplication
        min_fetch_magnitude: Minimum magnitude to fetch from USGS
        rate_limit: Rate limiting configuration
    """
    polling_interval_seconds: int = 60
    lookback_hours: int = 1
    monitoring_regions: list[MonitoringRegion] = field(default_factory=list)
    alert_channels: list[AlertChannel] = field(default_factory=list)
    points_of_interest: list[PointOfInterest] = field(default_factory=list)
    firestore_database: str | None = None
    firestore_collection: str = "earthquake_alerts"
    min_fetch_magnitude: float | None = None
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class ValidationError:
    """A configuration validation error.

    Attributes:
        field: The field that has an error
        message: Human-readable error description
        severity: 'error' or 'warning'
    """
    field: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    """Result of validating configuration.

    Attributes:
        valid: True if no errors (warnings are OK)
        errors: List of validation errors/warnings
    """
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def warnings(self) -> list[ValidationError]:
        """Get only warnings."""
        return [e for e in self.errors if e.severity == "warning"]

    @property
    def critical_errors(self) -> list[ValidationError]:
        """Get only critical errors."""
        return [e for e in self.errors if e.severity == "error"]


def validate_coordinates(lat: float, lon: float, field_name: str) -> list[ValidationError]:
    """Validate latitude/longitude coordinates.

    Pure function.

    Args:
        lat: Latitude value
        lon: Longitude value
        field_name: Name of the field for error messages

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not -90 <= lat <= 90:
        errors.append(ValidationError(
            field=field_name,
            message=f"Latitude {lat} out of range [-90, 90]",
        ))

    if not -180 <= lon <= 180:
        errors.append(ValidationError(
            field=field_name,
            message=f"Longitude {lon} out of range [-180, 180]",
        ))

    return errors


def validate_bounds(bounds: BoundingBox, field_name: str) -> list[ValidationError]:
    """Validate a bounding box.

    Pure function.

    Args:
        bounds: Bounding box to validate
        field_name: Name of the field for error messages

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Validate individual coordinates
    errors.extend(validate_coordinates(
        bounds.min_latitude, bounds.min_longitude,
        f"{field_name}.min",
    ))
    errors.extend(validate_coordinates(
        bounds.max_latitude, bounds.max_longitude,
        f"{field_name}.max",
    ))

    # Check min < max
    if bounds.min_latitude > bounds.max_latitude:
        errors.append(ValidationError(
            field=field_name,
            message=f"min_latitude ({bounds.min_latitude}) > max_latitude ({bounds.max_latitude})",
        ))

    if bounds.min_longitude > bounds.max_longitude:
        errors.append(ValidationError(
            field=field_name,
            message=f"min_longitude ({bounds.min_longitude}) > max_longitude ({bounds.max_longitude})",
        ))

    return errors


def validate_poi_references(
    referenced_names: set[str],
    available_pois: list[PointOfInterest],
    field_name: str,
) -> list[ValidationError]:
    """Validate that POI references exist.

    Pure function. Returns warnings for unmatched references.

    Args:
        referenced_names: POI names referenced in config
        available_pois: Available POIs to match against
        field_name: Name of the field for error messages

    Returns:
        List of validation warnings for unmatched references
    """
    available_names = {poi.name for poi in available_pois}
    unmatched = referenced_names - available_names

    errors = []
    for name in sorted(unmatched):
        # Find similar names for helpful suggestion
        similar = _find_similar_names(name, available_names)
        if similar:
            message = f"POI '{name}' not found. Did you mean '{similar[0]}'?"
        else:
            message = f"POI '{name}' not found in points_of_interest"

        errors.append(ValidationError(
            field=field_name,
            message=message,
            severity="warning",
        ))

    return errors


def _find_similar_names(name: str, candidates: set[str], threshold: float = 0.6) -> list[str]:
    """Find similar names using simple similarity metric.

    Pure function.

    Args:
        name: Name to match
        candidates: Available names
        threshold: Minimum similarity (0-1)

    Returns:
        Similar names sorted by similarity (best first)
    """
    def similarity(a: str, b: str) -> float:
        """Simple case-insensitive substring similarity."""
        a_lower, b_lower = a.lower(), b.lower()
        if a_lower == b_lower:
            return 1.0
        if a_lower in b_lower or b_lower in a_lower:
            return 0.8
        # Count common characters
        common = sum(1 for c in a_lower if c in b_lower)
        return common / max(len(a), len(b))

    scored = [(c, similarity(name, c)) for c in candidates]
    matches = [(c, s) for c, s in scored if s >= threshold]
    matches.sort(key=lambda x: x[1], reverse=True)

    return [c for c, _ in matches]


def validate_config(config: Config) -> ValidationResult:
    """Validate configuration for errors and warnings.

    Pure function.

    Args:
        config: Configuration to validate

    Returns:
        ValidationResult with any errors/warnings found
    """
    errors: list[ValidationError] = []

    # Validate monitoring regions
    for i, region in enumerate(config.monitoring_regions):
        errors.extend(validate_bounds(
            region.bounds,
            f"monitoring_regions[{i}].bounds",
        ))

    # Validate POIs
    for i, poi in enumerate(config.points_of_interest):
        errors.extend(validate_coordinates(
            poi.latitude, poi.longitude,
            f"points_of_interest[{i}]",
        ))
        if poi.alert_radius_km <= 0:
            errors.append(ValidationError(
                field=f"points_of_interest[{i}].alert_radius_km",
                message=f"Alert radius must be positive, got {poi.alert_radius_km}",
            ))

    # Validate alert channels
    for i, channel in enumerate(config.alert_channels):
        rules = channel.rules

        # Validate bounds if specified
        if rules.bounds is not None:
            errors.extend(validate_bounds(
                rules.bounds,
                f"alert_channels[{i}].rules.bounds",
            ))

        # Validate POI references
        if rules.points_of_interest:
            referenced = {poi.name for poi in rules.points_of_interest}
            # Note: POIs are already resolved, check against config.points_of_interest
            errors.extend(validate_poi_references(
                referenced,
                config.points_of_interest,
                f"alert_channels[{i}].rules.points_of_interest",
            ))

        # Validate magnitude range
        if rules.max_magnitude is not None and rules.min_magnitude > rules.max_magnitude:
            errors.append(ValidationError(
                field=f"alert_channels[{i}].rules",
                message=f"min_magnitude ({rules.min_magnitude}) > max_magnitude ({rules.max_magnitude})",
            ))

        # Warn about missing webhook
        if not channel.webhook_url or channel.webhook_url.startswith("${"):
            errors.append(ValidationError(
                field=f"alert_channels[{i}].webhook_url",
                message="Webhook URL not resolved (still contains placeholder)",
                severity="warning",
            ))

    # Check for no alert channels
    if not config.alert_channels:
        errors.append(ValidationError(
            field="alert_channels",
            message="No alert channels configured",
            severity="warning",
        ))

    has_critical = any(e.severity == "error" for e in errors)

    return ValidationResult(
        valid=not has_critical,
        errors=errors,
    )
