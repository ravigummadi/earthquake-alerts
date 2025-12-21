"""Slack Webhook Client - Imperative Shell.

This module handles HTTP communication with Slack webhooks.
All I/O is contained here; message formatting is in the core module.
"""

import logging
from dataclasses import dataclass
from typing import Any

import requests


logger = logging.getLogger(__name__)


# Default timeout for webhook requests (seconds)
DEFAULT_TIMEOUT = 10


@dataclass
class SlackResponse:
    """Response from Slack webhook.

    Attributes:
        success: Whether the message was sent successfully
        status_code: HTTP status code
        error: Error message if failed
    """
    success: bool
    status_code: int
    error: str | None = None


class SlackClient:
    """Client for sending messages to Slack via webhooks.

    This is part of the imperative shell - it handles HTTP I/O.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize Slack client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def send_message(
        self,
        webhook_url: str,
        payload: dict[str, Any],
    ) -> SlackResponse:
        """Send a message to Slack via webhook.

        This method performs HTTP I/O.

        Args:
            webhook_url: Slack incoming webhook URL
            payload: Message payload (from formatter)

        Returns:
            SlackResponse indicating success or failure
        """
        logger.info("Sending message to Slack webhook")

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                logger.info("Message sent successfully to Slack")
                return SlackResponse(
                    success=True,
                    status_code=response.status_code,
                )
            else:
                error_text = response.text
                logger.warning(
                    "Slack webhook returned non-200: %d - %s",
                    response.status_code,
                    error_text,
                )
                return SlackResponse(
                    success=False,
                    status_code=response.status_code,
                    error=error_text,
                )

        except requests.Timeout:
            logger.error("Slack webhook request timed out")
            return SlackResponse(
                success=False,
                status_code=0,
                error="Request timed out",
            )
        except requests.RequestException as e:
            logger.error("Slack webhook request failed: %s", str(e))
            return SlackResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    def send_messages(
        self,
        webhook_url: str,
        payloads: list[dict[str, Any]],
    ) -> list[SlackResponse]:
        """Send multiple messages to Slack.

        Args:
            webhook_url: Slack incoming webhook URL
            payloads: List of message payloads

        Returns:
            List of responses for each message
        """
        responses = []
        for payload in payloads:
            response = self.send_message(webhook_url, payload)
            responses.append(response)
        return responses
