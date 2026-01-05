"""Tests for the Orchestrator module.

Tests the coordination between functional core and imperative shell.
Uses mocks for shell components to test orchestration logic.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from src.orchestrator import Orchestrator, AlertResult, ProcessingResult
from src.core.earthquake import Earthquake
from src.core.config import Config, MonitoringRegion
from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel, AlertRule


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake for testing."""
    return Earthquake(
        id="us12345",
        magnitude=4.5,
        place="10km NE of San Francisco, CA",
        time=datetime(2023, 12, 19, 12, 0, 0, tzinfo=timezone.utc),
        latitude=37.7749,
        longitude=-122.4194,
        depth_km=10.5,
        url="https://earthquake.usgs.gov/earthquakes/eventpage/us12345",
        felt=150,
        alert="green",
        tsunami=False,
        mag_type="ml",
    )


@pytest.fixture
def sample_bounds():
    """Create sample bounding box for Bay Area."""
    return BoundingBox(
        min_latitude=36.0,
        max_latitude=38.5,
        min_longitude=-123.0,
        max_longitude=-121.0,
    )


@pytest.fixture
def slack_channel(sample_bounds):
    """Create a Slack alert channel."""
    return AlertChannel(
        name="test-slack",
        channel_type="slack",
        webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
        rules=AlertRule(
            min_magnitude=3.0,
            bounds=sample_bounds,
        ),
    )


@pytest.fixture
def twitter_channel():
    """Create a Twitter alert channel."""
    return AlertChannel(
        name="test-twitter",
        channel_type="twitter",
        webhook_url="",
        rules=AlertRule(min_magnitude=4.0),
        credentials=(
            ("api_key", "test_key"),
            ("api_secret", "test_secret"),
            ("access_token", "test_token"),
            ("access_token_secret", "test_token_secret"),
        ),
    )


@pytest.fixture
def whatsapp_channel():
    """Create a WhatsApp alert channel."""
    return AlertChannel(
        name="test-whatsapp",
        channel_type="whatsapp",
        webhook_url="",
        rules=AlertRule(min_magnitude=4.0),
        credentials=(
            ("account_sid", "test_sid"),
            ("auth_token", "test_token"),
            ("from_number", "+14155238886"),
            ("to_numbers", ("+1234567890",)),
        ),
    )


@pytest.fixture
def sample_config(sample_bounds, slack_channel):
    """Create a sample configuration."""
    return Config(
        polling_interval_seconds=60,
        lookback_hours=1,
        monitoring_regions=[
            MonitoringRegion(name="Bay Area", bounds=sample_bounds)
        ],
        alert_channels=[slack_channel],
    )


@pytest.fixture
def mock_usgs_client(sample_earthquake):
    """Create a mock USGS client."""
    client = Mock()
    # Return GeoJSON that will parse to our sample earthquake
    client.fetch_recent.return_value = {
        "features": [
            {
                "id": sample_earthquake.id,
                "properties": {
                    "mag": sample_earthquake.magnitude,
                    "place": sample_earthquake.place,
                    "time": int(sample_earthquake.time.timestamp() * 1000),
                    "url": sample_earthquake.url,
                    "felt": sample_earthquake.felt,
                    "alert": sample_earthquake.alert,
                    "tsunami": 0,
                    "magType": sample_earthquake.mag_type,
                    "types": "",
                },
                "geometry": {
                    "coordinates": [
                        sample_earthquake.longitude,
                        sample_earthquake.latitude,
                        sample_earthquake.depth_km,
                    ]
                },
            }
        ]
    }
    return client


@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client."""
    client = Mock()
    response = Mock()
    response.success = True
    response.error = None
    client.send_message.return_value = response
    return client


@pytest.fixture
def mock_twitter_client():
    """Create a mock Twitter client."""
    client = Mock()

    # Mock tweet response
    tweet_response = Mock()
    tweet_response.success = True
    tweet_response.error = None
    client.send_tweet.return_value = tweet_response

    # Mock media upload response
    upload_response = Mock()
    upload_response.success = True
    upload_response.media_id = "123456789"
    upload_response.error = None
    client.upload_media.return_value = upload_response

    return client


@pytest.fixture
def mock_whatsapp_client():
    """Create a mock WhatsApp client."""
    client = Mock()
    response = Mock()
    response.success = True
    response.error = None
    client.send_to_group.return_value = [response]
    return client


@pytest.fixture
def mock_firestore_client():
    """Create a mock Firestore client."""
    client = Mock()
    client.get_alerted_ids.return_value = set()  # No previously alerted
    client.add_alerted_ids.return_value = True
    return client


@pytest.fixture
def mock_static_map_client():
    """Create a mock static map client."""
    client = Mock()
    response = Mock()
    response.success = True
    response.image_bytes = b"fake_png_data"
    response.error = None
    client.generate_map.return_value = response
    return client


class TestAlertResult:
    """Tests for AlertResult dataclass."""

    def test_success_result(self, sample_earthquake, slack_channel):
        """Successful result has correct fields."""
        result = AlertResult(
            earthquake=sample_earthquake,
            channel=slack_channel,
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_failure_result(self, sample_earthquake, slack_channel):
        """Failure result includes error message."""
        result = AlertResult(
            earthquake=sample_earthquake,
            channel=slack_channel,
            success=False,
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"


class TestProcessingResult:
    """Tests for ProcessingResult dataclass."""

    def test_success_when_no_errors(self):
        """success property returns True when no errors."""
        result = ProcessingResult(
            earthquakes_fetched=5,
            earthquakes_new=2,
            alerts_sent=[],
            alerts_failed=[],
            errors=[],
        )
        assert result.success is True

    def test_failure_when_errors(self):
        """success property returns False when errors present."""
        result = ProcessingResult(
            earthquakes_fetched=5,
            earthquakes_new=2,
            alerts_sent=[],
            alerts_failed=[],
            errors=["Failed to connect"],
        )
        assert result.success is False

    def test_summary_format(self):
        """summary property returns readable string."""
        result = ProcessingResult(
            earthquakes_fetched=10,
            earthquakes_new=3,
            alerts_sent=[Mock()],
            alerts_failed=[Mock(), Mock()],
            errors=[],
        )
        summary = result.summary
        assert "10" in summary
        assert "3" in summary
        assert "1" in summary  # alerts sent
        assert "2" in summary  # alerts failed


class TestOrchestratorInit:
    """Tests for Orchestrator initialization."""

    def test_creates_default_clients(self, sample_config):
        """Creates default clients if not provided."""
        with patch('src.orchestrator.USGSClient'), \
             patch('src.orchestrator.SlackClient'), \
             patch('src.orchestrator.TwitterClient'), \
             patch('src.orchestrator.WhatsAppClient'), \
             patch('src.orchestrator.FirestoreClient'), \
             patch('src.orchestrator.StaticMapClient'):
            orchestrator = Orchestrator(sample_config)
            assert orchestrator.config == sample_config
            assert orchestrator.usgs_client is not None
            assert orchestrator.slack_client is not None
            assert orchestrator.twitter_client is not None
            assert orchestrator.whatsapp_client is not None
            assert orchestrator.firestore_client is not None
            assert orchestrator.static_map_client is not None

    def test_uses_provided_clients(
        self,
        sample_config,
        mock_usgs_client,
        mock_slack_client,
        mock_firestore_client,
    ):
        """Uses provided clients instead of creating new ones."""
        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            firestore_client=mock_firestore_client,
        )
        assert orchestrator.usgs_client == mock_usgs_client
        assert orchestrator.slack_client == mock_slack_client
        assert orchestrator.firestore_client == mock_firestore_client


class TestOrchestratorGetCombinedBounds:
    """Tests for _get_combined_bounds method."""

    def test_returns_combined_bounds(self, sample_config):
        """Returns combined bounds from all regions."""
        orchestrator = Orchestrator(sample_config)
        bounds = orchestrator._get_combined_bounds()

        assert bounds is not None
        assert bounds.min_latitude == 36.0
        assert bounds.max_latitude == 38.5

    def test_returns_none_for_no_regions(self):
        """Returns None when no monitoring regions."""
        config = Config()  # No regions
        orchestrator = Orchestrator(config)
        bounds = orchestrator._get_combined_bounds()

        assert bounds is None


class TestOrchestratorFetchEarthquakes:
    """Tests for _fetch_earthquakes method."""

    def test_fetches_and_parses_earthquakes(
        self,
        sample_config,
        mock_usgs_client,
        sample_earthquake,
    ):
        """Fetches earthquakes from USGS and parses them."""
        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
        )

        earthquakes = orchestrator._fetch_earthquakes()

        assert len(earthquakes) == 1
        assert earthquakes[0].id == sample_earthquake.id
        assert earthquakes[0].magnitude == sample_earthquake.magnitude

    def test_passes_bounds_to_usgs_client(
        self,
        sample_config,
        mock_usgs_client,
    ):
        """Passes combined bounds to USGS client."""
        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
        )

        orchestrator._fetch_earthquakes()

        call_args = mock_usgs_client.fetch_recent.call_args
        assert call_args.kwargs["bounds"] is not None


class TestOrchestratorSendSlackAlert:
    """Tests for _send_slack_alert method."""

    def test_sends_formatted_message(
        self,
        sample_config,
        mock_slack_client,
        sample_earthquake,
        slack_channel,
    ):
        """Sends formatted Slack message."""
        orchestrator = Orchestrator(
            sample_config,
            slack_client=mock_slack_client,
        )

        result = orchestrator._send_slack_alert(
            sample_earthquake,
            slack_channel,
            nearby_pois=[],
        )

        assert result.success is True
        mock_slack_client.send_message.assert_called_once()

        # Check payload includes magnitude
        call_args = mock_slack_client.send_message.call_args
        payload = call_args.args[1]
        assert "4.5" in str(payload)

    def test_returns_failure_on_error(
        self,
        sample_config,
        sample_earthquake,
        slack_channel,
    ):
        """Returns failure result when Slack client fails."""
        mock_client = Mock()
        response = Mock()
        response.success = False
        response.error = "Rate limited"
        mock_client.send_message.return_value = response

        orchestrator = Orchestrator(
            sample_config,
            slack_client=mock_client,
        )

        result = orchestrator._send_slack_alert(
            sample_earthquake,
            slack_channel,
            nearby_pois=[],
        )

        assert result.success is False
        assert result.error == "Rate limited"


class TestOrchestratorSendTwitterAlert:
    """Tests for _send_twitter_alert method."""

    def test_sends_tweet_with_credentials(
        self,
        sample_config,
        mock_twitter_client,
        mock_static_map_client,
        sample_earthquake,
        twitter_channel,
    ):
        """Sends tweet with provided credentials."""
        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
            static_map_client=mock_static_map_client,
        )

        result = orchestrator._send_twitter_alert(
            sample_earthquake,
            twitter_channel,
            nearby_pois=[],
        )

        assert result.success is True
        mock_twitter_client.send_tweet.assert_called_once()

    def test_uploads_map_image(
        self,
        sample_config,
        mock_twitter_client,
        mock_static_map_client,
        sample_earthquake,
        twitter_channel,
    ):
        """Uploads map image before sending tweet."""
        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
            static_map_client=mock_static_map_client,
        )

        orchestrator._send_twitter_alert(
            sample_earthquake,
            twitter_channel,
            nearby_pois=[],
        )

        # Map should be generated
        mock_static_map_client.generate_map.assert_called_once()
        # Media should be uploaded
        mock_twitter_client.upload_media.assert_called_once()
        # Tweet should include media_ids
        call_args = mock_twitter_client.send_tweet.call_args
        assert call_args.kwargs.get("media_ids") == ["123456789"]

    def test_fails_without_credentials(
        self,
        sample_config,
        mock_twitter_client,
        sample_earthquake,
    ):
        """Returns failure when credentials missing."""
        channel_no_creds = AlertChannel(
            name="twitter-no-creds",
            channel_type="twitter",
            webhook_url="",
            rules=AlertRule(min_magnitude=4.0),
            credentials=None,
        )

        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
        )

        result = orchestrator._send_twitter_alert(
            sample_earthquake,
            channel_no_creds,
            nearby_pois=[],
        )

        assert result.success is False
        assert "credentials" in result.error.lower()

    def test_fails_with_missing_credential_keys(
        self,
        sample_config,
        mock_twitter_client,
        sample_earthquake,
    ):
        """Returns failure when credential keys missing."""
        channel_bad_creds = AlertChannel(
            name="twitter-bad-creds",
            channel_type="twitter",
            webhook_url="",
            rules=AlertRule(min_magnitude=4.0),
            credentials=(("api_key", "test"),),  # Missing other keys
        )

        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
        )

        result = orchestrator._send_twitter_alert(
            sample_earthquake,
            channel_bad_creds,
            nearby_pois=[],
        )

        assert result.success is False
        assert "missing key" in result.error.lower()

    def test_continues_without_map_on_map_failure(
        self,
        sample_config,
        mock_twitter_client,
        sample_earthquake,
        twitter_channel,
    ):
        """Sends tweet without image when map generation fails."""
        mock_map_client = Mock()
        map_response = Mock()
        map_response.success = False
        map_response.error = "Map service unavailable"
        map_response.image_bytes = None
        mock_map_client.generate_map.return_value = map_response

        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
            static_map_client=mock_map_client,
        )

        result = orchestrator._send_twitter_alert(
            sample_earthquake,
            twitter_channel,
            nearby_pois=[],
        )

        # Should still send tweet successfully
        assert result.success is True
        # Tweet should be sent without media_ids
        call_args = mock_twitter_client.send_tweet.call_args
        assert call_args.kwargs.get("media_ids") is None


class TestOrchestratorSendWhatsAppAlert:
    """Tests for _send_whatsapp_alert method."""

    def test_sends_message_to_group(
        self,
        sample_config,
        mock_whatsapp_client,
        sample_earthquake,
        whatsapp_channel,
    ):
        """Sends message to all recipients."""
        orchestrator = Orchestrator(
            sample_config,
            whatsapp_client=mock_whatsapp_client,
        )

        result = orchestrator._send_whatsapp_alert(
            sample_earthquake,
            whatsapp_channel,
            nearby_pois=[],
        )

        assert result.success is True
        mock_whatsapp_client.send_to_group.assert_called_once()

    def test_fails_without_credentials(
        self,
        sample_config,
        mock_whatsapp_client,
        sample_earthquake,
    ):
        """Returns failure when credentials missing."""
        channel_no_creds = AlertChannel(
            name="whatsapp-no-creds",
            channel_type="whatsapp",
            webhook_url="",
            rules=AlertRule(min_magnitude=4.0),
            credentials=None,
        )

        orchestrator = Orchestrator(
            sample_config,
            whatsapp_client=mock_whatsapp_client,
        )

        result = orchestrator._send_whatsapp_alert(
            sample_earthquake,
            channel_no_creds,
            nearby_pois=[],
        )

        assert result.success is False
        assert "credentials" in result.error.lower()

    def test_fails_without_recipients(
        self,
        sample_config,
        mock_whatsapp_client,
        sample_earthquake,
    ):
        """Returns failure when no recipients configured."""
        channel_no_recipients = AlertChannel(
            name="whatsapp-no-recipients",
            channel_type="whatsapp",
            webhook_url="",
            rules=AlertRule(min_magnitude=4.0),
            credentials=(
                ("account_sid", "test_sid"),
                ("auth_token", "test_token"),
                ("from_number", "+14155238886"),
                # No to_numbers
            ),
        )

        orchestrator = Orchestrator(
            sample_config,
            whatsapp_client=mock_whatsapp_client,
        )

        result = orchestrator._send_whatsapp_alert(
            sample_earthquake,
            channel_no_recipients,
            nearby_pois=[],
        )

        assert result.success is False
        assert "recipients" in result.error.lower() or "to_numbers" in result.error.lower()

    def test_partial_success_on_some_failures(
        self,
        sample_config,
        sample_earthquake,
        whatsapp_channel,
    ):
        """Returns success when at least one message succeeds."""
        mock_client = Mock()
        success_response = Mock()
        success_response.success = True
        success_response.error = None

        failure_response = Mock()
        failure_response.success = False
        failure_response.error = "Invalid number"

        mock_client.send_to_group.return_value = [success_response, failure_response]

        orchestrator = Orchestrator(
            sample_config,
            whatsapp_client=mock_client,
        )

        result = orchestrator._send_whatsapp_alert(
            sample_earthquake,
            whatsapp_channel,
            nearby_pois=[],
        )

        # Should be success if at least one succeeded
        assert result.success is True
        # But should include error message
        assert "Invalid number" in result.error


class TestOrchestratorSendAlert:
    """Tests for _send_alert method (routing)."""

    def test_routes_to_slack(
        self,
        sample_config,
        mock_slack_client,
        sample_earthquake,
        slack_channel,
    ):
        """Routes Slack channel to Slack client."""
        orchestrator = Orchestrator(
            sample_config,
            slack_client=mock_slack_client,
        )

        orchestrator._send_alert(sample_earthquake, slack_channel)

        mock_slack_client.send_message.assert_called_once()

    def test_routes_to_twitter(
        self,
        sample_config,
        mock_twitter_client,
        mock_static_map_client,
        sample_earthquake,
        twitter_channel,
    ):
        """Routes Twitter channel to Twitter client."""
        orchestrator = Orchestrator(
            sample_config,
            twitter_client=mock_twitter_client,
            static_map_client=mock_static_map_client,
        )

        orchestrator._send_alert(sample_earthquake, twitter_channel)

        mock_twitter_client.send_tweet.assert_called_once()

    def test_routes_to_whatsapp(
        self,
        sample_config,
        mock_whatsapp_client,
        sample_earthquake,
        whatsapp_channel,
    ):
        """Routes WhatsApp channel to WhatsApp client."""
        orchestrator = Orchestrator(
            sample_config,
            whatsapp_client=mock_whatsapp_client,
        )

        orchestrator._send_alert(sample_earthquake, whatsapp_channel)

        mock_whatsapp_client.send_to_group.assert_called_once()

    def test_default_to_slack_for_unknown_type(
        self,
        sample_config,
        mock_slack_client,
        sample_earthquake,
    ):
        """Defaults to Slack for unknown channel types."""
        unknown_channel = AlertChannel(
            name="unknown",
            channel_type="discord",  # Not implemented
            webhook_url="https://example.com/webhook",
            rules=AlertRule(min_magnitude=4.0),
        )

        orchestrator = Orchestrator(
            sample_config,
            slack_client=mock_slack_client,
        )

        orchestrator._send_alert(sample_earthquake, unknown_channel)

        mock_slack_client.send_message.assert_called_once()


class TestOrchestratorProcess:
    """Tests for process method (main entry point)."""

    def test_full_processing_cycle(
        self,
        sample_config,
        mock_usgs_client,
        mock_slack_client,
        mock_firestore_client,
        sample_earthquake,
    ):
        """Tests complete processing cycle."""
        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        assert result.earthquakes_fetched == 1
        assert result.earthquakes_new == 1
        assert len(result.alerts_sent) == 1
        assert len(result.alerts_failed) == 0
        assert result.success is True

    def test_returns_early_on_fetch_error(
        self,
        sample_config,
        mock_firestore_client,
    ):
        """Returns error result when fetch fails."""
        mock_usgs = Mock()
        mock_usgs.fetch_recent.side_effect = Exception("Network error")

        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        assert result.success is False
        assert "Failed to fetch" in result.errors[0]
        assert result.earthquakes_fetched == 0

    def test_returns_empty_result_when_no_earthquakes(
        self,
        sample_config,
        mock_firestore_client,
    ):
        """Returns empty result when no earthquakes found."""
        mock_usgs = Mock()
        mock_usgs.fetch_recent.return_value = {"features": []}

        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        assert result.success is True
        assert result.earthquakes_fetched == 0
        assert result.earthquakes_new == 0

    def test_filters_already_alerted_earthquakes(
        self,
        sample_config,
        mock_usgs_client,
        mock_slack_client,
    ):
        """Filters out earthquakes that were already alerted."""
        mock_firestore = Mock()
        mock_firestore.get_alerted_ids.return_value = {"us12345"}  # Already alerted
        mock_firestore.add_alerted_ids.return_value = True

        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            firestore_client=mock_firestore,
        )

        result = orchestrator.process()

        assert result.earthquakes_fetched == 1
        assert result.earthquakes_new == 0
        assert len(result.alerts_sent) == 0
        mock_slack_client.send_message.assert_not_called()

    def test_stores_alerted_ids_on_success(
        self,
        sample_config,
        mock_usgs_client,
        mock_slack_client,
        mock_firestore_client,
    ):
        """Stores alerted IDs in Firestore after successful alerts."""
        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            firestore_client=mock_firestore_client,
        )

        orchestrator.process()

        mock_firestore_client.add_alerted_ids.assert_called_once()
        call_args = mock_firestore_client.add_alerted_ids.call_args
        assert "us12345" in call_args.args[0]

    def test_does_not_store_ids_on_failed_alert(
        self,
        sample_config,
        mock_usgs_client,
        mock_firestore_client,
    ):
        """Does not store IDs when alert fails."""
        mock_slack = Mock()
        response = Mock()
        response.success = False
        response.error = "Webhook error"
        mock_slack.send_message.return_value = response

        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        assert len(result.alerts_failed) == 1
        # Should not store ID since alert failed
        mock_firestore_client.add_alerted_ids.assert_not_called()

    def test_records_firestore_error(
        self,
        sample_config,
        mock_usgs_client,
        mock_slack_client,
    ):
        """Records error when Firestore update fails."""
        mock_firestore = Mock()
        mock_firestore.get_alerted_ids.return_value = set()
        mock_firestore.add_alerted_ids.return_value = False  # Fails

        orchestrator = Orchestrator(
            sample_config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            firestore_client=mock_firestore,
        )

        result = orchestrator.process()

        assert "deduplication" in result.errors[0].lower()

    def test_multi_channel_routing(
        self,
        sample_bounds,
        mock_usgs_client,
        mock_slack_client,
        mock_twitter_client,
        mock_static_map_client,
        mock_firestore_client,
    ):
        """Routes earthquake to multiple channels."""
        slack_channel = AlertChannel(
            name="slack",
            channel_type="slack",
            webhook_url="https://hooks.slack.com/test",
            rules=AlertRule(min_magnitude=3.0, bounds=sample_bounds),
        )
        twitter_channel = AlertChannel(
            name="twitter",
            channel_type="twitter",
            webhook_url="",
            rules=AlertRule(min_magnitude=3.0, bounds=sample_bounds),
            credentials=(
                ("api_key", "test"),
                ("api_secret", "test"),
                ("access_token", "test"),
                ("access_token_secret", "test"),
            ),
        )

        config = Config(
            monitoring_regions=[MonitoringRegion(name="Bay Area", bounds=sample_bounds)],
            alert_channels=[slack_channel, twitter_channel],
        )

        orchestrator = Orchestrator(
            config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack_client,
            twitter_client=mock_twitter_client,
            static_map_client=mock_static_map_client,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        assert len(result.alerts_sent) == 2
        mock_slack_client.send_message.assert_called_once()
        mock_twitter_client.send_tweet.assert_called_once()

    def test_partial_channel_failure(
        self,
        sample_bounds,
        mock_usgs_client,
        mock_twitter_client,
        mock_static_map_client,
        mock_firestore_client,
    ):
        """Handles partial failure (one channel fails, one succeeds)."""
        # Slack will fail
        mock_slack = Mock()
        slack_response = Mock()
        slack_response.success = False
        slack_response.error = "Rate limited"
        mock_slack.send_message.return_value = slack_response

        slack_channel = AlertChannel(
            name="slack",
            channel_type="slack",
            webhook_url="https://hooks.slack.com/test",
            rules=AlertRule(min_magnitude=3.0, bounds=sample_bounds),
        )
        twitter_channel = AlertChannel(
            name="twitter",
            channel_type="twitter",
            webhook_url="",
            rules=AlertRule(min_magnitude=3.0, bounds=sample_bounds),
            credentials=(
                ("api_key", "test"),
                ("api_secret", "test"),
                ("access_token", "test"),
                ("access_token_secret", "test"),
            ),
        )

        config = Config(
            monitoring_regions=[MonitoringRegion(name="Bay Area", bounds=sample_bounds)],
            alert_channels=[slack_channel, twitter_channel],
        )

        orchestrator = Orchestrator(
            config,
            usgs_client=mock_usgs_client,
            slack_client=mock_slack,
            twitter_client=mock_twitter_client,
            static_map_client=mock_static_map_client,
            firestore_client=mock_firestore_client,
        )

        result = orchestrator.process()

        # One success, one failure
        assert len(result.alerts_sent) == 1
        assert len(result.alerts_failed) == 1

        # ID should NOT be stored since not all channels succeeded
        mock_firestore_client.add_alerted_ids.assert_not_called()
