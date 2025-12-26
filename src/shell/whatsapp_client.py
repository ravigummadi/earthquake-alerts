"""WhatsApp Client via Twilio - Imperative Shell.

This module handles sending WhatsApp messages via Twilio's WhatsApp API.
All I/O is contained here; message formatting is in the core module.
"""

import logging
from dataclasses import dataclass

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


logger = logging.getLogger(__name__)


# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30


@dataclass
class WhatsAppResponse:
    """Response from WhatsApp send attempt.

    Attributes:
        success: Whether the message was sent successfully
        message_sid: Twilio message SID if successful
        error: Error message if failed
    """
    success: bool
    message_sid: str | None = None
    error: str | None = None


@dataclass
class WhatsAppCredentials:
    """Twilio credentials for WhatsApp API.

    Attributes:
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        from_number: WhatsApp sender number (format: whatsapp:+14155238886)
    """
    account_sid: str
    auth_token: str
    from_number: str


class WhatsAppClient:
    """Client for sending WhatsApp messages via Twilio.

    This is part of the imperative shell - it handles I/O.
    Uses Twilio's WhatsApp Business API.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize WhatsApp client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def send_message(
        self,
        text: str,
        to_number: str,
        credentials: WhatsAppCredentials,
    ) -> WhatsAppResponse:
        """Send a WhatsApp message via Twilio.

        This method performs HTTP I/O.

        Args:
            text: Message text
            to_number: Recipient WhatsApp number (format: whatsapp:+1234567890)
            credentials: Twilio credentials

        Returns:
            WhatsAppResponse indicating success or failure
        """
        logger.info("Sending WhatsApp message via Twilio")

        # Ensure numbers have whatsapp: prefix
        from_number = credentials.from_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        try:
            client = Client(credentials.account_sid, credentials.auth_token)

            message = client.messages.create(
                body=text,
                from_=from_number,
                to=to_number,
            )

            logger.info("WhatsApp message sent: %s", message.sid)
            return WhatsAppResponse(
                success=True,
                message_sid=message.sid,
            )

        except TwilioRestException as e:
            logger.error("Twilio API error: %s", str(e))
            return WhatsAppResponse(
                success=False,
                error=f"Twilio error: {e.msg}",
            )
        except Exception as e:
            logger.error("WhatsApp send failed: %s", str(e))
            return WhatsAppResponse(
                success=False,
                error=str(e),
            )

    def send_to_group(
        self,
        text: str,
        to_numbers: list[str],
        credentials: WhatsAppCredentials,
        stop_on_error: bool = False,
    ) -> list[WhatsAppResponse]:
        """Send a WhatsApp message to multiple recipients.

        This is a deep method that handles:
        - Sending to multiple recipients
        - Optional early termination on error
        - Consistent response collection

        Args:
            text: Message text
            to_numbers: List of recipient WhatsApp numbers
            credentials: Twilio credentials
            stop_on_error: If True, stop sending on first error

        Returns:
            List of responses for each recipient
        """
        responses = []

        for to_number in to_numbers:
            response = self.send_message(text, to_number, credentials)
            responses.append(response)

            if stop_on_error and not response.success:
                logger.warning(
                    "Stopping batch send after error sending to %s",
                    to_number,
                )
                break

        return responses
