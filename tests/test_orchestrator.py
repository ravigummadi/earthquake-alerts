"""Unit tests for the Orchestrator module.

Verifies coordination between functional core and imperative shell.
All network, Firestore, Slack, Twitter, and WhatsApp services are strictly mocked.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import Config, MonitoringRegion
from src.core.earthquake import Earthquake
from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel, AlertDecision, AlertRule
from src.orchestrator import AlertResult, Orchestrator, ProcessingResult
from src.shell.firestore_client import FirestoreClient
from src.shell.slack_client import SlackClient, SlackResponse
from src.shell.static_map_client import MapImageResult, StaticMapClient
from src.shell.twitter_client import (
    MediaUploadResponse,
    TwitterClient,
    TwitterResponse,
)
from src.shell.usgs_client import USGSClient
from src.shell.whatsapp_client import WhatsAppClient, WhatsAppResponse


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake for orchestrator tests."""
    return Earthquake(
        id="nc75095866",
        magnitude=5.2,
        place="10km NE of San Francisco, CA",
        time=datetime(2023, 12, 19, 16, 0, 0, tzinfo=timezone.utc),
        latitude=37.7749,
        longitude=-122.4194,
        depth_km=10.5,
        url="https://earthquake.usgs.gov/earthquakes/eventpage/nc75095866",
        felt=250,
        alert="yellow",
        tsunami=False,
    )


@pytest.fixture
def sample_slack_channel():
    """Create a sample Slack alert channel."""
    return AlertChannel(
        name="slack-critical",
        channel_type="slack",
        webhook_url="https://hooks.slack.com/services/T00/B00/XXX",
        rules=AlertRule(min_magnitude=4.0),
    )


@pytest.fixture
def twitter_credentials():
    """Sample Twitter credentials tuple."""
    return (
        ("api_key", "test_api_key"),
        ("api_secret", "test_api_secret"),
        ("access_token", "test_access_token"),
        ("access_token_secret", "test_access_token_secret"),
    )


@pytest.fixture
def whatsapp_credentials():
    """Sample WhatsApp credentials tuple."""
    return (
        ("account_sid", "ACtest123"),
        ("auth_token", "token456"),
        ("from_number", "whatsapp:+14155238886"),
        ("to_numbers", ("whatsapp:+15551234567", "whatsapp:+15557654321")),
    )


@pytest.fixture
def sample_config(sample_slack_channel):
    """Create a standard Config instance for testing."""
    return Config(
        polling_interval_seconds=60,
        lookback_hours=1,
        monitoring_regions=[
            MonitoringRegion(
                name="Bay Area",
                bounds=BoundingBox(
                    min_latitude=36.0,
                    max_latitude=39.0,
                    min_longitude=-123.5,
                    max_longitude=-121.0,
                ),
            )
        ],
        alert_channels=[sample_slack_channel],
        firestore_database="(default)",
        firestore_collection="test_alerts",
        min_fetch_magnitude=2.5,
    )


class TestAlertResult:
    """Tests for AlertResult dataclass."""

    def test_alert_result_attributes_and_defaults(
        self, sample_earthquake, sample_slack_channel
    ):
        """AlertResult correctly stores attributes and defaults error to None."""
        result = AlertResult(
            earthquake=sample_earthquake,
            channel=sample_slack_channel,
            success=True,
        )
        assert result.earthquake == sample_earthquake
        assert result.channel == sample_slack_channel
        assert result.success is True
        assert result.error is None

    def test_alert_result_with_error(
        self, sample_earthquake, sample_slack_channel
    ):
        """AlertResult captures error messages on failure."""
        result = AlertResult(
            earthquake=sample_earthquake,
            channel=sample_slack_channel,
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


class TestProcessingResult:
    """Tests for ProcessingResult dataclass and properties."""

    def test_success_property_true_when_no_errors(
        self, sample_earthquake, sample_slack_channel
    ):
        """ProcessingResult.success is True when errors list is empty."""
        result = ProcessingResult(
            earthquakes_fetched=5,
            earthquakes_new=3,
            alerts_sent=[
                AlertResult(sample_earthquake, sample_slack_channel, True)
            ],
            alerts_failed=[],
            errors=[],
        )
        assert result.success is True

    def test_success_property_false_when_errors_present(self):
        """ProcessingResult.success is False when errors list is non-empty."""
        result = ProcessingResult(
            earthquakes_fetched=0,
            earthquakes_new=0,
            alerts_sent=[],
            alerts_failed=[],
            errors=["Failed to connect to database"],
        )
        assert result.success is False

    def test_summary_property_formatting(
        self, sample_earthquake, sample_slack_channel
    ):
        """ProcessingResult.summary provides structured human-readable count."""
        sent = [AlertResult(sample_earthquake, sample_slack_channel, True)]
        failed = [
            AlertResult(
                sample_earthquake, sample_slack_channel, False, "HTTP 500"
            )
        ]
        result = ProcessingResult(
            earthquakes_fetched=10,
            earthquakes_new=4,
            alerts_sent=sent,
            alerts_failed=failed,
            errors=[],
        )
        assert (
            result.summary
            == "Fetched 10 earthquakes, 4 new, 1 alerts sent, 1 failed"
        )


class TestOrchestratorInitialization:
    """Tests for Orchestrator initialization and dependency injection."""

    def test_init_with_injected_mocks(self, sample_config):
        """Orchestrator stores provided mock clients without creating defaults."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_slack = MagicMock(spec=SlackClient)
        mock_twitter = MagicMock(spec=TwitterClient)
        mock_whatsapp = MagicMock(spec=WhatsAppClient)
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_map = MagicMock(spec=StaticMapClient)

        orchestrator = Orchestrator(
            config=sample_config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            twitter_client=mock_twitter,
            whatsapp_client=mock_whatsapp,
            firestore_client=mock_firestore,
            static_map_client=mock_map,
        )

        assert orchestrator.config == sample_config
        assert orchestrator.usgs_client is mock_usgs
        assert orchestrator.slack_client is mock_slack
        assert orchestrator.twitter_client is mock_twitter
        assert orchestrator.whatsapp_client is mock_whatsapp
        assert orchestrator.firestore_client is mock_firestore
        assert orchestrator.static_map_client is mock_map

    def test_init_with_defaults_creates_all_clients(self, sample_config):
        """Default initialization instantiates shell clients with config settings."""
        with (
            patch("src.orchestrator.USGSClient") as mock_usgs_cls,
            patch("src.orchestrator.SlackClient") as mock_slack_cls,
            patch("src.orchestrator.TwitterClient") as mock_tw_cls,
            patch("src.orchestrator.WhatsAppClient") as mock_wa_cls,
            patch("src.orchestrator.StaticMapClient") as mock_map_cls,
            patch("src.orchestrator.FirestoreClient") as mock_fs_cls,
        ):
            orch = Orchestrator(config=sample_config)

            mock_usgs_cls.assert_called_once_with()
            mock_slack_cls.assert_called_once_with()
            mock_tw_cls.assert_called_once_with()
            mock_wa_cls.assert_called_once_with()
            mock_map_cls.assert_called_once_with()
            mock_fs_cls.assert_called_once()
            fs_config_arg = mock_fs_cls.call_args[0][0]
            assert fs_config_arg.database == sample_config.firestore_database
            assert (
                fs_config_arg.collection == sample_config.firestore_collection
            )


class TestOrchestratorCombinedBounds:
    """Tests for Orchestrator._get_combined_bounds()."""

    def test_empty_monitoring_regions_returns_none(self):
        """Returns None if config has no monitoring regions."""
        config = Config(monitoring_regions=[])
        orch = Orchestrator(
            config=config,
            usgs_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        assert orch._get_combined_bounds() is None

    def test_single_monitoring_region_returns_its_bounds(self):
        """Returns the region's bounding box when exactly one is defined."""
        box = BoundingBox(35.0, 40.0, -125.0, -120.0)
        config = Config(monitoring_regions=[MonitoringRegion("Single", box)])
        orch = Orchestrator(
            config=config,
            usgs_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        assert orch._get_combined_bounds() == box

    def test_multiple_monitoring_regions_combined(self):
        """Combines multiple region bounds into single encompassing bounding box."""
        box1 = BoundingBox(36.0, 38.0, -123.0, -121.0)
        box2 = BoundingBox(32.0, 34.0, -119.0, -116.0)
        config = Config(
            monitoring_regions=[
                MonitoringRegion("North", box1),
                MonitoringRegion("South", box2),
            ]
        )
        orch = Orchestrator(
            config=config,
            usgs_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        combined = orch._get_combined_bounds()
        assert combined == BoundingBox(
            min_latitude=32.0,
            max_latitude=38.0,
            min_longitude=-123.0,
            max_longitude=-116.0,
        )


class TestOrchestratorFetchEarthquakes:
    """Tests for Orchestrator._fetch_earthquakes()."""

    def test_fetches_and_parses_earthquakes(self, sample_config):
        """Calls USGS client with configuration parameters and parses GeoJSON."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq1",
                    "properties": {
                        "mag": 4.8,
                        "place": "Central California",
                        "time": 1703001600000,
                        "url": "https://example.com/eq1",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-121.5, 36.8, 8.0],
                    },
                }
            ],
        }
        orch = Orchestrator(
            config=sample_config,
            usgs_client=mock_usgs,
            firestore_client=MagicMock(),
        )

        earthquakes = orch._fetch_earthquakes()

        assert len(earthquakes) == 1
        assert earthquakes[0].id == "eq1"
        assert earthquakes[0].magnitude == 4.8
        mock_usgs.fetch_recent.assert_called_once_with(
            bounds=sample_config.monitoring_regions[0].bounds,
            min_magnitude=sample_config.min_fetch_magnitude,
            hours=sample_config.lookback_hours,
        )


class TestOrchestratorSendAlertRouting:
    """Tests for channel routing in Orchestrator._send_alert()."""

    def test_routes_to_slack_by_default(self, sample_config, sample_earthquake):
        """Routes to _send_slack_alert for channel_type 'slack' or unknown types."""
        orch = Orchestrator(
            config=sample_config,
            slack_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        slack_channel = AlertChannel(
            "general", "slack", "https://hook", AlertRule()
        )
        custom_channel = AlertChannel(
            "custom", "other", "https://hook", AlertRule()
        )

        with patch.object(orch, "_send_slack_alert") as mock_slack:
            mock_slack.return_value = AlertResult(
                sample_earthquake, slack_channel, True
            )
            orch._send_alert(sample_earthquake, slack_channel)
            mock_slack.assert_called_once()

        with patch.object(orch, "_send_slack_alert") as mock_slack:
            mock_slack.return_value = AlertResult(
                sample_earthquake, custom_channel, True
            )
            orch._send_alert(sample_earthquake, custom_channel)
            mock_slack.assert_called_once()

    def test_routes_to_twitter(self, sample_config, sample_earthquake):
        """Routes to _send_twitter_alert when channel_type is 'twitter'."""
        orch = Orchestrator(
            config=sample_config,
            twitter_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        twitter_channel = AlertChannel("x-feed", "twitter", "", AlertRule())

        with patch.object(orch, "_send_twitter_alert") as mock_twitter:
            mock_twitter.return_value = AlertResult(
                sample_earthquake, twitter_channel, True
            )
            res = orch._send_alert(sample_earthquake, twitter_channel)
            mock_twitter.assert_called_once()
            assert res.success is True

    def test_routes_to_whatsapp(self, sample_config, sample_earthquake):
        """Routes to _send_whatsapp_alert when channel_type is 'whatsapp'."""
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=MagicMock(),
            firestore_client=MagicMock(),
        )
        wa_channel = AlertChannel("wa-team", "whatsapp", "", AlertRule())

        with patch.object(orch, "_send_whatsapp_alert") as mock_wa:
            mock_wa.return_value = AlertResult(
                sample_earthquake, wa_channel, True
            )
            res = orch._send_alert(sample_earthquake, wa_channel)
            mock_wa.assert_called_once()
            assert res.success is True


class TestOrchestratorSlackAlerts:
    """Tests for Orchestrator._send_slack_alert()."""

    def test_slack_send_successful(
        self, sample_config, sample_earthquake, sample_slack_channel
    ):
        """Successful Slack send returns AlertResult with success=True."""
        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=True, status_code=200, error=None
        )
        orch = Orchestrator(
            config=sample_config,
            slack_client=mock_slack,
            firestore_client=MagicMock(),
        )

        result = orch._send_slack_alert(
            sample_earthquake, sample_slack_channel, []
        )

        assert result.success is True
        assert result.error is None
        assert result.earthquake == sample_earthquake
        assert result.channel == sample_slack_channel
        mock_slack.send_message.assert_called_once()

    def test_slack_send_failed(
        self, sample_config, sample_earthquake, sample_slack_channel
    ):
        """Failed Slack send returns AlertResult with success=False and error."""
        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=False, status_code=404, error="Channel not found"
        )
        orch = Orchestrator(
            config=sample_config,
            slack_client=mock_slack,
            firestore_client=MagicMock(),
        )

        result = orch._send_slack_alert(
            sample_earthquake, sample_slack_channel, []
        )

        assert result.success is False
        assert result.error == "Channel not found"


class TestOrchestratorTwitterAlerts:
    """Tests for Orchestrator._send_twitter_alert()."""

    def test_missing_credentials_returns_error(
        self, sample_config, sample_earthquake
    ):
        """Twitter channel without credentials fails before network attempts."""
        channel = AlertChannel(
            "twitter-feed", "twitter", "", AlertRule(), credentials=None
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=MagicMock(),
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert result.error == "Twitter channel missing credentials"

    def test_missing_credential_keys_returns_error(
        self, sample_config, sample_earthquake
    ):
        """Twitter channel with incomplete credentials tuple fails with missing key."""
        incomplete_creds = (
            ("api_key", "key1"),
            ("api_secret", "secret1"),
            ("access_token", "token1"),
            # missing access_token_secret
        )
        channel = AlertChannel(
            "twitter-feed", "twitter", "", AlertRule(), credentials=incomplete_creds
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=MagicMock(),
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert "Twitter credentials missing key" in (result.error or "")

    def test_twitter_success_with_map_and_media(
        self, sample_config, sample_earthquake, twitter_credentials
    ):
        """Generates static map, uploads media, and sends tweet with media ID."""
        mock_map = MagicMock(spec=StaticMapClient)
        mock_map.generate_map.return_value = MapImageResult(
            success=True, image_bytes=b"fake_png_data"
        )
        mock_tw = MagicMock(spec=TwitterClient)
        mock_tw.upload_media.return_value = MediaUploadResponse(
            success=True, status_code=200, media_id="media_12345"
        )
        mock_tw.send_tweet.return_value = TwitterResponse(
            success=True, status_code=201, tweet_id="tweet_789"
        )

        channel = AlertChannel(
            "twitter-feed",
            "twitter",
            "",
            AlertRule(),
            credentials=twitter_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=mock_tw,
            static_map_client=mock_map,
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is True
        assert result.error is None
        mock_map.generate_map.assert_called_once()
        mock_tw.upload_media.assert_called_once()
        assert mock_tw.send_tweet.call_args[1]["media_ids"] == ["media_12345"]

    def test_twitter_media_upload_failure_continues_without_media(
        self, sample_config, sample_earthquake, twitter_credentials
    ):
        """Falls back to sending text tweet when media upload fails."""
        mock_map = MagicMock(spec=StaticMapClient)
        mock_map.generate_map.return_value = MapImageResult(
            success=True, image_bytes=b"fake_png_data"
        )
        mock_tw = MagicMock(spec=TwitterClient)
        mock_tw.upload_media.return_value = MediaUploadResponse(
            success=False, status_code=400, error="Media file too large"
        )
        mock_tw.send_tweet.return_value = TwitterResponse(
            success=True, status_code=201, tweet_id="tweet_789"
        )

        channel = AlertChannel(
            "twitter-feed",
            "twitter",
            "",
            AlertRule(),
            credentials=twitter_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=mock_tw,
            static_map_client=mock_map,
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is True
        assert mock_tw.send_tweet.call_args[1]["media_ids"] is None

    def test_twitter_map_generation_failure_continues_without_media(
        self, sample_config, sample_earthquake, twitter_credentials
    ):
        """Falls back to text tweet when map generation fails."""
        mock_map = MagicMock(spec=StaticMapClient)
        mock_map.generate_map.return_value = MapImageResult(
            success=False, error="Tile provider unavailable"
        )
        mock_tw = MagicMock(spec=TwitterClient)
        mock_tw.send_tweet.return_value = TwitterResponse(
            success=True, status_code=201, tweet_id="tweet_789"
        )

        channel = AlertChannel(
            "twitter-feed",
            "twitter",
            "",
            AlertRule(),
            credentials=twitter_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=mock_tw,
            static_map_client=mock_map,
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is True
        mock_tw.upload_media.assert_not_called()
        assert mock_tw.send_tweet.call_args[1]["media_ids"] is None

    def test_twitter_send_tweet_failure(
        self, sample_config, sample_earthquake, twitter_credentials
    ):
        """Twitter API error propagates into AlertResult."""
        mock_map = MagicMock(spec=StaticMapClient)
        mock_map.generate_map.return_value = MapImageResult(success=False)
        mock_tw = MagicMock(spec=TwitterClient)
        mock_tw.send_tweet.return_value = TwitterResponse(
            success=False, status_code=403, error="Rate limit exceeded"
        )

        channel = AlertChannel(
            "twitter-feed",
            "twitter",
            "",
            AlertRule(),
            credentials=twitter_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            twitter_client=mock_tw,
            static_map_client=mock_map,
            firestore_client=MagicMock(),
        )

        result = orch._send_twitter_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert result.error == "Rate limit exceeded"


class TestOrchestratorWhatsAppAlerts:
    """Tests for Orchestrator._send_whatsapp_alert()."""

    def test_missing_credentials_returns_error(
        self, sample_config, sample_earthquake
    ):
        """WhatsApp channel without credentials fails immediately."""
        channel = AlertChannel(
            "wa-alerts", "whatsapp", "", AlertRule(), credentials=None
        )
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=MagicMock(),
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert result.error == "WhatsApp channel missing credentials"

    def test_missing_credential_keys_returns_error(
        self, sample_config, sample_earthquake
    ):
        """WhatsApp channel missing required credentials key returns error."""
        incomplete_creds = (
            ("account_sid", "AC123"),
            ("from_number", "whatsapp:+14155238886"),
            # missing auth_token
        )
        channel = AlertChannel(
            "wa-alerts", "whatsapp", "", AlertRule(), credentials=incomplete_creds
        )
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=MagicMock(),
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert "WhatsApp credentials missing key" in (result.error or "")

    def test_missing_recipients_returns_error(
        self, sample_config, sample_earthquake
    ):
        """WhatsApp channel with empty to_numbers returns error."""
        creds = (
            ("account_sid", "AC123"),
            ("auth_token", "secret"),
            ("from_number", "whatsapp:+14155238886"),
            ("to_numbers", ()),
        )
        channel = AlertChannel(
            "wa-alerts", "whatsapp", "", AlertRule(), credentials=creds
        )
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=MagicMock(),
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert (
            result.error == "WhatsApp channel has no recipients (to_numbers)"
        )

    def test_single_string_recipient_handled(
        self, sample_config, sample_earthquake
    ):
        """to_numbers given as a single string is wrapped and delivered."""
        creds = (
            ("account_sid", "AC123"),
            ("auth_token", "secret"),
            ("from_number", "whatsapp:+14155238886"),
            ("to_numbers", "whatsapp:+15551234567"),
        )
        channel = AlertChannel(
            "wa-alerts", "whatsapp", "", AlertRule(), credentials=creds
        )
        mock_wa = MagicMock(spec=WhatsAppClient)
        mock_wa.send_to_group.return_value = [
            WhatsAppResponse(success=True, message_sid="SM111")
        ]
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=mock_wa,
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is True
        mock_wa.send_to_group.assert_called_once()
        assert mock_wa.send_to_group.call_args[0][1] == [
            "whatsapp:+15551234567"
        ]

    def test_group_send_partial_success(
        self, sample_config, sample_earthquake, whatsapp_credentials
    ):
        """If at least one recipient succeeds, result is success=True with error logged."""
        mock_wa = MagicMock(spec=WhatsAppClient)
        mock_wa.send_to_group.return_value = [
            WhatsAppResponse(success=True, message_sid="SM111"),
            WhatsAppResponse(success=False, error="User unsubscribed"),
        ]
        channel = AlertChannel(
            "wa-alerts",
            "whatsapp",
            "",
            AlertRule(),
            credentials=whatsapp_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=mock_wa,
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is True
        assert result.error == "User unsubscribed"

    def test_group_send_all_fail(
        self, sample_config, sample_earthquake, whatsapp_credentials
    ):
        """If all recipients fail, result is success=False with joined error strings."""
        mock_wa = MagicMock(spec=WhatsAppClient)
        mock_wa.send_to_group.return_value = [
            WhatsAppResponse(success=False, error="Network error"),
            WhatsAppResponse(success=False, error="Invalid recipient"),
        ]
        channel = AlertChannel(
            "wa-alerts",
            "whatsapp",
            "",
            AlertRule(),
            credentials=whatsapp_credentials,
        )
        orch = Orchestrator(
            config=sample_config,
            whatsapp_client=mock_wa,
            firestore_client=MagicMock(),
        )

        result = orch._send_whatsapp_alert(sample_earthquake, channel, [])

        assert result.success is False
        assert result.error == "Network error; Invalid recipient"


class TestOrchestratorProcessLifecycle:
    """Comprehensive lifecycle tests for Orchestrator.process()."""

    def test_process_fetch_earthquakes_exception_handled(self, sample_config):
        """Step 1: Network/HTTP error during fetch returns failure ProcessingResult."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.side_effect = ConnectionError("USGS API down")
        orch = Orchestrator(
            config=sample_config,
            usgs_client=mock_usgs,
            firestore_client=MagicMock(),
        )

        result = orch.process()

        assert result.success is False
        assert result.earthquakes_fetched == 0
        assert result.earthquakes_new == 0
        assert len(result.alerts_sent) == 0
        assert len(result.alerts_failed) == 0
        assert result.errors == ["Failed to fetch earthquakes: USGS API down"]

    def test_process_empty_usgs_feed(self, sample_config):
        """Step 1: Empty USGS feed short-circuits gracefully without calling Firestore."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        orch = Orchestrator(
            config=sample_config,
            usgs_client=mock_usgs,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is True
        assert result.earthquakes_fetched == 0
        assert result.earthquakes_new == 0
        assert len(result.alerts_sent) == 0
        assert len(result.alerts_failed) == 0
        assert len(result.errors) == 0
        mock_firestore.get_alerted_ids.assert_not_called()

    def test_process_all_earthquakes_already_alerted(self, sample_config):
        """Step 2: When all earthquakes are already in Firestore, no alerts are triggered."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_old_1",
                    "properties": {
                        "mag": 4.5,
                        "time": 1703001600000,
                        "place": "SF",
                        "url": "https://example.com/1",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4, 37.8, 10.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = {"eq_old_1"}
        orch = Orchestrator(
            config=sample_config,
            usgs_client=mock_usgs,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is True
        assert result.earthquakes_fetched == 1
        assert result.earthquakes_new == 0
        assert len(result.alerts_sent) == 0
        mock_firestore.add_alerted_ids.assert_not_called()

    def test_process_new_earthquake_does_not_match_rules(self):
        """Step 3: New earthquake that does not meet rule thresholds produces no alerts."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_minor",
                    "properties": {
                        "mag": 2.1,
                        "time": 1703001600000,
                        "place": "SF",
                        "url": "https://example.com/minor",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4, 37.8, 10.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()

        # Rule requires M >= 5.0
        channel = AlertChannel(
            "crit", "slack", "https://hook", AlertRule(min_magnitude=5.0)
        )
        config = Config(alert_channels=[channel])
        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is True
        assert result.earthquakes_fetched == 1
        assert result.earthquakes_new == 1
        assert len(result.alerts_sent) == 0
        mock_firestore.add_alerted_ids.assert_not_called()

    def test_process_happy_path_alerts_and_deduplicates(self):
        """Step 4 & 5: Alert matches rule, succeeds, and persists new ID to Firestore."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_major",
                    "properties": {
                        "mag": 5.8,
                        "time": 1703001600000,
                        "place": "San Jose, CA",
                        "url": "https://example.com/major",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-121.9, 37.3, 12.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()
        mock_firestore.add_alerted_ids.return_value = True

        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=True, status_code=200
        )

        channel = AlertChannel(
            "major-alerts",
            "slack",
            "https://hooks.slack.com/test",
            AlertRule(min_magnitude=5.0),
        )
        config = Config(alert_channels=[channel])
        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is True
        assert result.earthquakes_fetched == 1
        assert result.earthquakes_new == 1
        assert len(result.alerts_sent) == 1
        assert len(result.alerts_failed) == 0
        assert result.alerts_sent[0].earthquake.id == "eq_major"
        mock_firestore.add_alerted_ids.assert_called_once_with({"eq_major"})

    def test_process_firestore_dedup_update_failure(self):
        """Step 5: When Firestore add_alerted_ids returns False, error is reported in result."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_fail_fs",
                    "properties": {
                        "mag": 4.5,
                        "time": 1703001600000,
                        "place": "SF",
                        "url": "https://example.com/fs",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4, 37.8, 10.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()
        mock_firestore.add_alerted_ids.return_value = False  # DB write failure

        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=True, status_code=200
        )

        channel = AlertChannel(
            "all", "slack", "https://hook", AlertRule(min_magnitude=3.0)
        )
        config = Config(alert_channels=[channel])
        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is False
        assert "Failed to update deduplication state" in result.errors
        assert len(result.alerts_sent) == 1

    def test_process_all_channels_fail_no_dedup_update(self):
        """Step 4 & 5: When all notification channels fail, earthquake is not marked alerted."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_failed_send",
                    "properties": {
                        "mag": 4.5,
                        "time": 1703001600000,
                        "place": "SF",
                        "url": "https://example.com/fs",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4, 37.8, 10.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()

        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=False, status_code=500, error="Slack outage"
        )

        channel = AlertChannel(
            "all", "slack", "https://hook", AlertRule(min_magnitude=3.0)
        )
        config = Config(alert_channels=[channel])
        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.success is True  # Orchestration completed without crash
        assert len(result.alerts_sent) == 0
        assert len(result.alerts_failed) == 1
        assert result.alerts_failed[0].error == "Slack outage"
        mock_firestore.add_alerted_ids.assert_not_called()

    def test_process_multi_channel_partial_success_marks_alerted(
        self, twitter_credentials
    ):
        """Earthquake is marked alerted if ANY channel succeeds (prevents duplicates)."""
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "eq_partial",
                    "properties": {
                        "mag": 5.0,
                        "time": 1703001600000,
                        "place": "SF",
                        "url": "https://example.com/p",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4, 37.8, 10.0],
                    },
                }
            ],
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()
        mock_firestore.add_alerted_ids.return_value = True

        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=True, status_code=200
        )

        mock_tw = MagicMock(spec=TwitterClient)
        mock_tw.send_tweet.return_value = TwitterResponse(
            success=False, status_code=500, error="Twitter down"
        )

        mock_map = MagicMock(spec=StaticMapClient)
        mock_map.generate_map.return_value = MapImageResult(success=False)

        ch_slack = AlertChannel(
            "slack-crit", "slack", "https://hook", AlertRule(min_magnitude=4.0)
        )
        ch_twitter = AlertChannel(
            "twitter-feed",
            "twitter",
            "",
            AlertRule(min_magnitude=4.0),
            credentials=twitter_credentials,
        )
        config = Config(alert_channels=[ch_slack, ch_twitter])

        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            twitter_client=mock_tw,
            static_map_client=mock_map,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert len(result.alerts_sent) == 1
        assert len(result.alerts_failed) == 1
        mock_firestore.add_alerted_ids.assert_called_once_with({"eq_partial"})

    def test_process_duplicate_earthquakes_in_feed_handled(self):
        """Feed with duplicated earthquake IDs avoids duplicate Firestore IDs."""
        eq_feature = {
            "type": "Feature",
            "id": "eq_dup_feed",
            "properties": {
                "mag": 4.5,
                "time": 1703001600000,
                "place": "SF",
                "url": "https://example.com/dup",
            },
            "geometry": {"type": "Point", "coordinates": [-122.4, 37.8, 10.0]},
        }
        mock_usgs = MagicMock(spec=USGSClient)
        mock_usgs.fetch_recent.return_value = {
            "type": "FeatureCollection",
            "features": [eq_feature, eq_feature],  # Repeated ID in USGS feed
        }
        mock_firestore = MagicMock(spec=FirestoreClient)
        mock_firestore.get_alerted_ids.return_value = set()
        mock_firestore.add_alerted_ids.return_value = True

        mock_slack = MagicMock(spec=SlackClient)
        mock_slack.send_message.return_value = SlackResponse(
            success=True, status_code=200
        )

        channel = AlertChannel(
            "slack", "slack", "https://hook", AlertRule(min_magnitude=4.0)
        )
        config = Config(alert_channels=[channel])
        orch = Orchestrator(
            config=config,
            usgs_client=mock_usgs,
            slack_client=mock_slack,
            firestore_client=mock_firestore,
        )

        result = orch.process()

        assert result.earthquakes_fetched == 2
        assert result.earthquakes_new == 2
        # Deduplication set passed to Firestore contains only unique ID
        mock_firestore.add_alerted_ids.assert_called_once_with({"eq_dup_feed"})
