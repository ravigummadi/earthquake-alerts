"""Orchestrator - Wires Functional Core and Imperative Shell.

This module coordinates the flow of data between the pure functional
core and the I/O-performing shell components. It's the "glue" that
makes the application work.
"""

import logging
from dataclasses import dataclass

from src.core.earthquake import Earthquake, parse_earthquakes
from src.core.dedup import filter_already_alerted, compute_ids_to_store
from src.core.formatter import format_slack_message, get_nearby_pois
from src.core.rules import AlertChannel, make_alert_decisions, AlertDecision
from src.core.geo import BoundingBox

from src.shell.usgs_client import USGSClient
from src.shell.slack_client import SlackClient
from src.shell.firestore_client import FirestoreClient, FirestoreConfig
from src.shell.config_loader import Config


logger = logging.getLogger(__name__)


@dataclass
class AlertResult:
    """Result of processing a single earthquake alert.

    Attributes:
        earthquake: The earthquake that was processed
        channel: The channel alert was sent to
        success: Whether the alert was sent successfully
        error: Error message if failed
    """
    earthquake: Earthquake
    channel: AlertChannel
    success: bool
    error: str | None = None


@dataclass
class ProcessingResult:
    """Result of a complete earthquake monitoring cycle.

    Attributes:
        earthquakes_fetched: Total earthquakes fetched from USGS
        earthquakes_new: Earthquakes not previously alerted
        alerts_sent: Successfully sent alerts
        alerts_failed: Failed alert attempts
        errors: Any errors that occurred
    """
    earthquakes_fetched: int
    earthquakes_new: int
    alerts_sent: list[AlertResult]
    alerts_failed: list[AlertResult]
    errors: list[str]

    @property
    def success(self) -> bool:
        """Returns True if no critical errors occurred."""
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        """Human-readable summary of the processing result."""
        return (
            f"Fetched {self.earthquakes_fetched} earthquakes, "
            f"{self.earthquakes_new} new, "
            f"{len(self.alerts_sent)} alerts sent, "
            f"{len(self.alerts_failed)} failed"
        )


class Orchestrator:
    """Coordinates earthquake monitoring and alerting.

    This class wires together:
    - USGS client (fetches earthquake data)
    - Core functions (parsing, rules, formatting)
    - Firestore client (deduplication state)
    - Slack client (sending notifications)
    """

    def __init__(
        self,
        config: Config,
        usgs_client: USGSClient | None = None,
        slack_client: SlackClient | None = None,
        firestore_client: FirestoreClient | None = None,
    ) -> None:
        """Initialize orchestrator with configuration.

        Args:
            config: Application configuration
            usgs_client: USGS client (created if not provided)
            slack_client: Slack client (created if not provided)
            firestore_client: Firestore client (created if not provided)
        """
        self.config = config
        self.usgs_client = usgs_client or USGSClient()
        self.slack_client = slack_client or SlackClient()
        self.firestore_client = firestore_client or FirestoreClient(
            FirestoreConfig(collection=config.firestore_collection)
        )

    def _get_combined_bounds(self) -> BoundingBox | None:
        """Get combined bounding box from all monitoring regions."""
        if not self.config.monitoring_regions:
            return None

        # Combine all regions into one bounding box
        min_lat = min(r.bounds.min_latitude for r in self.config.monitoring_regions)
        max_lat = max(r.bounds.max_latitude for r in self.config.monitoring_regions)
        min_lon = min(r.bounds.min_longitude for r in self.config.monitoring_regions)
        max_lon = max(r.bounds.max_longitude for r in self.config.monitoring_regions)

        return BoundingBox(
            min_latitude=min_lat,
            max_latitude=max_lat,
            min_longitude=min_lon,
            max_longitude=max_lon,
        )

    def _fetch_earthquakes(self) -> list[Earthquake]:
        """Fetch earthquakes from USGS API.

        Returns:
            List of parsed earthquakes
        """
        bounds = self._get_combined_bounds()

        geojson = self.usgs_client.fetch_recent(
            bounds=bounds,
            min_magnitude=self.config.min_fetch_magnitude,
            hours=self.config.lookback_hours,
        )

        # Pure core function
        return parse_earthquakes(geojson)

    def _send_alert(
        self,
        earthquake: Earthquake,
        channel: AlertChannel,
    ) -> AlertResult:
        """Send an alert for an earthquake to a channel.

        Args:
            earthquake: The earthquake to alert on
            channel: The channel to send to

        Returns:
            AlertResult indicating success or failure
        """
        # Get nearby POIs for context (pure core function)
        nearby_pois = get_nearby_pois(
            earthquake,
            list(channel.rules.points_of_interest),
            max_distance_km=100,
        )

        # Format message (pure core function)
        payload = format_slack_message(
            earthquake,
            channel_name=channel.name,
            nearby_pois=nearby_pois,
        )

        # Send via shell
        response = self.slack_client.send_message(
            channel.webhook_url,
            payload,
        )

        return AlertResult(
            earthquake=earthquake,
            channel=channel,
            success=response.success,
            error=response.error,
        )

    def _process_decision(self, decision: AlertDecision) -> list[AlertResult]:
        """Process a single alert decision.

        Args:
            decision: Alert decision with earthquake and channels

        Returns:
            List of alert results
        """
        results = []

        for channel in decision.channels:
            result = self._send_alert(decision.earthquake, channel)
            results.append(result)

            if result.success:
                logger.info(
                    "Sent alert for M%.1f %s to %s",
                    decision.earthquake.magnitude,
                    decision.earthquake.place,
                    channel.name,
                )
            else:
                logger.error(
                    "Failed to send alert for M%.1f %s to %s: %s",
                    decision.earthquake.magnitude,
                    decision.earthquake.place,
                    channel.name,
                    result.error,
                )

        return results

    def process(self) -> ProcessingResult:
        """Run a complete earthquake monitoring cycle.

        This is the main entry point that:
        1. Fetches earthquakes from USGS
        2. Filters out already-alerted earthquakes
        3. Evaluates alert rules
        4. Sends notifications
        5. Updates deduplication state

        Returns:
            ProcessingResult with details of what happened
        """
        errors: list[str] = []
        alerts_sent: list[AlertResult] = []
        alerts_failed: list[AlertResult] = []

        # Step 1: Fetch earthquakes
        try:
            earthquakes = self._fetch_earthquakes()
            logger.info("Fetched %d earthquakes from USGS", len(earthquakes))
        except Exception as e:
            error_msg = f"Failed to fetch earthquakes: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                earthquakes_fetched=0,
                earthquakes_new=0,
                alerts_sent=[],
                alerts_failed=[],
                errors=[error_msg],
            )

        if not earthquakes:
            logger.info("No earthquakes found")
            return ProcessingResult(
                earthquakes_fetched=0,
                earthquakes_new=0,
                alerts_sent=[],
                alerts_failed=[],
                errors=[],
            )

        # Step 2: Filter already-alerted (deduplication)
        alerted_ids = self.firestore_client.get_alerted_ids()
        new_earthquakes = filter_already_alerted(earthquakes, alerted_ids)

        logger.info(
            "%d new earthquakes (of %d total)",
            len(new_earthquakes),
            len(earthquakes),
        )

        if not new_earthquakes:
            return ProcessingResult(
                earthquakes_fetched=len(earthquakes),
                earthquakes_new=0,
                alerts_sent=[],
                alerts_failed=[],
                errors=[],
            )

        # Step 3: Evaluate alert rules (pure core function)
        decisions = make_alert_decisions(
            new_earthquakes,
            self.config.alert_channels,
        )

        logger.info(
            "%d earthquakes match alert rules",
            len(decisions),
        )

        # Step 4: Send notifications
        successfully_alerted: list[Earthquake] = []

        for decision in decisions:
            results = self._process_decision(decision)

            for result in results:
                if result.success:
                    alerts_sent.append(result)
                    if result.earthquake not in successfully_alerted:
                        successfully_alerted.append(result.earthquake)
                else:
                    alerts_failed.append(result)

        # Step 5: Update deduplication state
        if successfully_alerted:
            new_ids = compute_ids_to_store(successfully_alerted)
            if not self.firestore_client.add_alerted_ids(new_ids):
                errors.append("Failed to update deduplication state")

        return ProcessingResult(
            earthquakes_fetched=len(earthquakes),
            earthquakes_new=len(new_earthquakes),
            alerts_sent=alerts_sent,
            alerts_failed=alerts_failed,
            errors=errors,
        )
