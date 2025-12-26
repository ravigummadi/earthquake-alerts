"""Tests for WhatsApp client via Twilio.

Uses unittest.mock to mock Twilio API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.shell.whatsapp_client import (
    WhatsAppClient,
    WhatsAppResponse,
    WhatsAppCredentials,
)


# Test credentials
TEST_CREDS = WhatsAppCredentials(
    account_sid="test_account_sid",
    auth_token="test_auth_token",
    from_number="whatsapp:+14155238886",
)


class TestWhatsAppClientSendMessage:
    """Tests for WhatsAppClient.send_message()."""

    @patch("src.shell.whatsapp_client.Client")
    def test_successful_send_returns_success(self, mock_client_class):
        """Successful send returns WhatsAppResponse with success=True."""
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_message = Mock()
        mock_message.sid = "SM1234567890"
        mock_client.messages.create.return_value = mock_message

        client = WhatsAppClient()
        result = client.send_message(
            "Test message",
            "whatsapp:+1234567890",
            TEST_CREDS,
        )

        assert result.success is True
        assert result.message_sid == "SM1234567890"
        assert result.error is None

    @patch("src.shell.whatsapp_client.Client")
    def test_adds_whatsapp_prefix_to_numbers(self, mock_client_class):
        """Numbers without whatsapp: prefix get it added."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_message = Mock()
        mock_message.sid = "SM123"
        mock_client.messages.create.return_value = mock_message

        creds = WhatsAppCredentials(
            account_sid="test",
            auth_token="test",
            from_number="+14155238886",  # No whatsapp: prefix
        )

        client = WhatsAppClient()
        client.send_message("Test", "+1234567890", creds)

        # Verify prefixes were added
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["from_"].startswith("whatsapp:")
        assert call_kwargs["to"].startswith("whatsapp:")

    @patch("src.shell.whatsapp_client.Client")
    def test_twilio_error_returns_failure(self, mock_client_class):
        """Twilio API error returns failure with error message."""
        from twilio.base.exceptions import TwilioRestException

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create.side_effect = TwilioRestException(
            status=400,
            uri="/test",
            msg="Invalid phone number",
        )

        client = WhatsAppClient()
        result = client.send_message(
            "Test message",
            "whatsapp:+1234567890",
            TEST_CREDS,
        )

        assert result.success is False
        assert "Invalid phone number" in result.error

    @patch("src.shell.whatsapp_client.Client")
    def test_general_exception_returns_failure(self, mock_client_class):
        """General exception returns failure with error message."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Connection failed")

        client = WhatsAppClient()
        result = client.send_message(
            "Test message",
            "whatsapp:+1234567890",
            TEST_CREDS,
        )

        assert result.success is False
        assert "Connection failed" in result.error


class TestWhatsAppClientSendToGroup:
    """Tests for WhatsAppClient.send_to_group() batch method."""

    @patch("src.shell.whatsapp_client.Client")
    def test_sends_to_all_recipients(self, mock_client_class):
        """All recipients receive the message."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_message = Mock()
        mock_message.sid = "SM123"
        mock_client.messages.create.return_value = mock_message

        client = WhatsAppClient()
        to_numbers = ["+1111111111", "+2222222222", "+3333333333"]
        results = client.send_to_group("Test", to_numbers, TEST_CREDS)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_client.messages.create.call_count == 3

    @patch("src.shell.whatsapp_client.Client")
    def test_continues_on_error_by_default(self, mock_client_class):
        """Continues sending after error when stop_on_error=False."""
        from twilio.base.exceptions import TwilioRestException

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # First succeeds, second fails, third succeeds
        mock_message = Mock()
        mock_message.sid = "SM123"
        mock_client.messages.create.side_effect = [
            mock_message,
            TwilioRestException(400, "/test", "Invalid number"),
            mock_message,
        ]

        client = WhatsAppClient()
        to_numbers = ["+1111111111", "+2222222222", "+3333333333"]
        results = client.send_to_group("Test", to_numbers, TEST_CREDS)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

    @patch("src.shell.whatsapp_client.Client")
    def test_stops_on_error_when_requested(self, mock_client_class):
        """Stops sending after error when stop_on_error=True."""
        from twilio.base.exceptions import TwilioRestException

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_message = Mock()
        mock_message.sid = "SM123"
        mock_client.messages.create.side_effect = [
            mock_message,
            TwilioRestException(400, "/test", "Invalid number"),
            mock_message,
        ]

        client = WhatsAppClient()
        to_numbers = ["+1111111111", "+2222222222", "+3333333333"]
        results = client.send_to_group(
            "Test", to_numbers, TEST_CREDS, stop_on_error=True
        )

        # Should stop after the error
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        # Third message should not have been sent
        assert mock_client.messages.create.call_count == 2

    def test_empty_recipients_returns_empty_list(self):
        """Empty recipients list returns empty results."""
        client = WhatsAppClient()
        results = client.send_to_group("Test", [], TEST_CREDS)

        assert results == []


class TestWhatsAppResponse:
    """Tests for WhatsAppResponse dataclass."""

    def test_success_response(self):
        """Successful response has correct fields."""
        response = WhatsAppResponse(
            success=True,
            message_sid="SM1234567890",
        )

        assert response.success is True
        assert response.message_sid == "SM1234567890"
        assert response.error is None

    def test_failure_response(self):
        """Failure response includes error message."""
        response = WhatsAppResponse(
            success=False,
            error="Invalid phone number",
        )

        assert response.success is False
        assert response.message_sid is None
        assert response.error == "Invalid phone number"


class TestWhatsAppCredentials:
    """Tests for WhatsAppCredentials dataclass."""

    def test_credentials_fields(self):
        """Credentials dataclass has all required fields."""
        creds = WhatsAppCredentials(
            account_sid="AC123",
            auth_token="token123",
            from_number="+14155238886",
        )

        assert creds.account_sid == "AC123"
        assert creds.auth_token == "token123"
        assert creds.from_number == "+14155238886"
