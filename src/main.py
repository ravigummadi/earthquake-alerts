"""Cloud Function Entry Point.

This module provides the entry point for Google Cloud Functions.
It's a thin wrapper that loads configuration and invokes the orchestrator.
"""

import logging
import os
import json
from typing import Any

import functions_framework
from flask import Request

from src.orchestrator import Orchestrator
from src.shell.config_loader import load_config, load_config_from_env


# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_config():
    """Load configuration from file or environment."""
    config_path = os.environ.get("CONFIG_PATH")

    if config_path:
        return load_config(config_path)
    elif os.environ.get("SLACK_WEBHOOK_URL"):
        # Simple env-based config
        return load_config_from_env()
    else:
        # Try default config path
        return load_config()


@functions_framework.http
def earthquake_monitor(request: Request) -> tuple[dict[str, Any], int]:
    """HTTP Cloud Function entry point.

    This function is triggered by Cloud Scheduler or direct HTTP requests.
    It runs a complete earthquake monitoring cycle.

    Args:
        request: Flask request object (not used, but required by framework)

    Returns:
        Tuple of (response dict, HTTP status code)
    """
    logger.info("Starting earthquake monitoring cycle")

    try:
        # Load configuration
        config = _get_config()

        if not config.alert_channels:
            logger.warning("No alert channels configured")
            return {
                "status": "error",
                "message": "No alert channels configured",
            }, 400

        # Create and run orchestrator
        orchestrator = Orchestrator(config)
        result = orchestrator.process()

        # Build response
        response = {
            "status": "success" if result.success else "partial_failure",
            "summary": result.summary,
            "earthquakes_fetched": result.earthquakes_fetched,
            "earthquakes_new": result.earthquakes_new,
            "alerts_sent": len(result.alerts_sent),
            "alerts_failed": len(result.alerts_failed),
        }

        if result.errors:
            response["errors"] = result.errors

        # Log details
        if result.alerts_sent:
            for alert in result.alerts_sent:
                logger.info(
                    "Alert sent: M%.1f %s -> %s",
                    alert.earthquake.magnitude,
                    alert.earthquake.place,
                    alert.channel.name,
                )

        logger.info("Completed: %s", result.summary)

        status_code = 200 if result.success else 207  # 207 = Multi-Status
        return response, status_code

    except Exception as e:
        logger.exception("Unexpected error in earthquake monitor")
        return {
            "status": "error",
            "message": str(e),
        }, 500


@functions_framework.cloud_event
def earthquake_monitor_pubsub(cloud_event: Any) -> None:
    """Pub/Sub Cloud Function entry point.

    Alternative trigger for Cloud Scheduler via Pub/Sub.

    Args:
        cloud_event: CloudEvent from Pub/Sub
    """
    logger.info("Starting earthquake monitoring cycle (Pub/Sub trigger)")

    try:
        config = _get_config()

        if not config.alert_channels:
            logger.warning("No alert channels configured")
            return

        orchestrator = Orchestrator(config)
        result = orchestrator.process()

        logger.info("Completed: %s", result.summary)

        if result.errors:
            for error in result.errors:
                logger.error("Error: %s", error)

    except Exception as e:
        logger.exception("Unexpected error in earthquake monitor")
        raise


# For local testing
if __name__ == "__main__":
    import sys

    # Simple local test
    print("Running earthquake monitor locally...")

    # Check for config
    if not os.environ.get("SLACK_WEBHOOK_URL") and not os.path.exists("config/config.yaml"):
        print("Error: Set SLACK_WEBHOOK_URL or create config/config.yaml")
        sys.exit(1)

    # Mock request for local testing
    class MockRequest:
        pass

    response, status = earthquake_monitor(MockRequest())
    print(f"\nResponse ({status}):")
    print(json.dumps(response, indent=2))
