"""Tests for the Configuration Loader module.

Tests configuration loading from YAML files and environment variables.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.shell.config_loader import (
    load_config,
    load_config_from_dict,
    load_config_from_env,
    _resolve_value,
    _parse_bounds,
    _parse_poi,
    _parse_alert_rule,
    _parse_channel,
    _parse_region,
    _get_secret_manager_client,
)
from src.core.config import Config, MonitoringRegion
from src.core.geo import BoundingBox, PointOfInterest
from src.core.rules import AlertChannel, AlertRule


class TestResolvValue:
    """Tests for _resolve_value function."""

    def test_returns_non_string_unchanged(self):
        """Non-string values are returned unchanged."""
        assert _resolve_value(123) == 123
        assert _resolve_value(None) is None
        assert _resolve_value(True) is True

    def test_returns_plain_string_unchanged(self):
        """Plain strings without placeholders are returned unchanged."""
        assert _resolve_value("hello") == "hello"
        assert _resolve_value("https://example.com") == "https://example.com"

    def test_resolves_env_var_placeholder(self):
        """Resolves ${VAR} placeholders from environment."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = _resolve_value("${TEST_VAR}")
            assert result == "test_value"

    def test_returns_placeholder_if_env_var_not_set(self):
        """Returns original placeholder if env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the var if it exists
            os.environ.pop("UNDEFINED_VAR", None)
            result = _resolve_value("${UNDEFINED_VAR}")
            assert result == "${UNDEFINED_VAR}"

    def test_uses_secret_client_when_provided(self):
        """Uses secret client for resolution when provided."""
        mock_client = Mock()
        mock_client.resolve.return_value = "secret_value"

        result = _resolve_value("${secret:my-secret}", mock_client)

        mock_client.resolve.assert_called_once_with("${secret:my-secret}")
        assert result == "secret_value"

    def test_ignores_secret_placeholder_without_client(self):
        """Returns secret placeholder unchanged when no client."""
        result = _resolve_value("${secret:my-secret}", None)
        assert result == "${secret:my-secret}"


class TestParseBounds:
    """Tests for _parse_bounds function."""

    def test_parses_valid_bounds(self):
        """Parses valid bounding box data."""
        data = {
            "min_latitude": 36.0,
            "max_latitude": 38.5,
            "min_longitude": -123.0,
            "max_longitude": -121.0,
        }

        result = _parse_bounds(data)

        assert result.min_latitude == 36.0
        assert result.max_latitude == 38.5
        assert result.min_longitude == -123.0
        assert result.max_longitude == -121.0

    def test_converts_string_values_to_float(self):
        """Converts string values to floats."""
        data = {
            "min_latitude": "36.0",
            "max_latitude": "38.5",
            "min_longitude": "-123.0",
            "max_longitude": "-121.0",
        }

        result = _parse_bounds(data)

        assert result.min_latitude == 36.0
        assert isinstance(result.min_latitude, float)


class TestParsePoi:
    """Tests for _parse_poi function."""

    def test_parses_valid_poi(self):
        """Parses valid POI data."""
        data = {
            "name": "San Francisco",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "alert_radius_km": 50,
        }

        result = _parse_poi(data)

        assert result.name == "San Francisco"
        assert result.latitude == 37.7749
        assert result.longitude == -122.4194
        assert result.alert_radius_km == 50

    def test_uses_default_alert_radius(self):
        """Uses default alert radius when not specified."""
        data = {
            "name": "Test Location",
            "latitude": 37.0,
            "longitude": -122.0,
        }

        result = _parse_poi(data)

        assert result.alert_radius_km == 50  # Default value


class TestParseAlertRule:
    """Tests for _parse_alert_rule function."""

    def test_parses_minimal_rule(self):
        """Parses rule with minimal fields."""
        data = {"min_magnitude": 3.0}
        result = _parse_alert_rule(data, [])

        assert result.min_magnitude == 3.0
        assert result.max_magnitude is None
        assert result.bounds is None

    def test_parses_rule_with_bounds(self):
        """Parses rule with bounding box."""
        data = {
            "min_magnitude": 4.0,
            "bounds": {
                "min_latitude": 36.0,
                "max_latitude": 38.5,
                "min_longitude": -123.0,
                "max_longitude": -121.0,
            },
        }

        result = _parse_alert_rule(data, [])

        assert result.bounds is not None
        assert result.bounds.min_latitude == 36.0

    def test_parses_rule_with_pois(self):
        """Parses rule with points of interest references."""
        pois = [
            PointOfInterest("San Francisco", 37.7749, -122.4194, 50),
            PointOfInterest("Oakland", 37.8044, -122.2712, 30),
        ]
        data = {
            "min_magnitude": 3.0,
            "points_of_interest": ["San Francisco"],
        }

        result = _parse_alert_rule(data, pois)

        assert len(result.points_of_interest) == 1
        assert result.points_of_interest[0].name == "San Francisco"

    def test_parses_special_conditions(self):
        """Parses special alert conditions."""
        data = {
            "min_magnitude": 2.0,
            "alert_on_tsunami": False,
            "alert_on_felt": True,
            "felt_threshold": 100,
        }

        result = _parse_alert_rule(data, [])

        assert result.alert_on_tsunami is False
        assert result.alert_on_felt is True
        assert result.felt_threshold == 100


class TestParseChannel:
    """Tests for _parse_channel function."""

    def test_parses_slack_channel(self):
        """Parses Slack channel configuration."""
        data = {
            "name": "test-alerts",
            "type": "slack",
            "webhook_url": "https://hooks.slack.com/services/T00/B00/XXX",
            "rules": {"min_magnitude": 3.0},
        }

        result = _parse_channel(data, [])

        assert result.name == "test-alerts"
        assert result.channel_type == "slack"
        assert result.webhook_url == "https://hooks.slack.com/services/T00/B00/XXX"
        assert result.rules.min_magnitude == 3.0

    def test_parses_twitter_channel(self):
        """Parses Twitter channel with credentials."""
        data = {
            "name": "twitter-alerts",
            "type": "twitter",
            "credentials": {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "access_token": "test_token",
                "access_token_secret": "test_token_secret",
            },
            "rules": {"min_magnitude": 4.0},
        }

        result = _parse_channel(data, [])

        assert result.name == "twitter-alerts"
        assert result.channel_type == "twitter"
        assert result.credentials is not None
        # Credentials are stored as tuple of tuples
        creds_dict = dict(result.credentials)
        assert creds_dict["api_key"] == "test_key"

    def test_parses_whatsapp_channel(self):
        """Parses WhatsApp channel with credentials including to_numbers list."""
        data = {
            "name": "whatsapp-alerts",
            "type": "whatsapp",
            "credentials": {
                "account_sid": "test_sid",
                "auth_token": "test_token",
                "from_number": "+14155238886",
                "to_numbers": ["+1234567890", "+0987654321"],
            },
            "rules": {"min_magnitude": 5.0},
        }

        result = _parse_channel(data, [])

        assert result.name == "whatsapp-alerts"
        assert result.channel_type == "whatsapp"
        assert result.credentials is not None
        creds_dict = dict(result.credentials)
        # Lists should be converted to tuples
        assert creds_dict["to_numbers"] == ("+1234567890", "+0987654321")

    def test_defaults_to_slack_type(self):
        """Defaults to Slack type when not specified."""
        data = {
            "name": "default-channel",
            "webhook_url": "https://example.com/webhook",
            "rules": {"min_magnitude": 3.0},
        }

        result = _parse_channel(data, [])

        assert result.channel_type == "slack"

    def test_resolves_webhook_url_secret(self):
        """Resolves secret placeholder in webhook URL."""
        mock_client = Mock()
        mock_client.resolve.return_value = "https://resolved-webhook.com"

        data = {
            "name": "secret-channel",
            "webhook_url": "${secret:slack-webhook}",
            "rules": {"min_magnitude": 3.0},
        }

        result = _parse_channel(data, [], mock_client)

        assert result.webhook_url == "https://resolved-webhook.com"

    def test_resolves_credential_secrets(self):
        """Resolves secret placeholders in credentials."""
        mock_client = Mock()
        mock_client.resolve.side_effect = lambda x: x.replace("${secret:", "").replace("}", "_resolved")

        data = {
            "name": "twitter-alerts",
            "type": "twitter",
            "credentials": {
                "api_key": "${secret:twitter-api-key}",
                "api_secret": "${secret:twitter-api-secret}",
                "access_token": "plain_token",
                "access_token_secret": "plain_secret",
            },
            "rules": {"min_magnitude": 4.0},
        }

        result = _parse_channel(data, [], mock_client)

        creds_dict = dict(result.credentials)
        assert creds_dict["api_key"] == "twitter-api-key_resolved"
        assert creds_dict["access_token"] == "plain_token"


class TestParseRegion:
    """Tests for _parse_region function."""

    def test_parses_valid_region(self):
        """Parses valid region data."""
        data = {
            "name": "Bay Area",
            "bounds": {
                "min_latitude": 36.0,
                "max_latitude": 38.5,
                "min_longitude": -123.0,
                "max_longitude": -121.0,
            },
        }

        result = _parse_region(data)

        assert result.name == "Bay Area"
        assert result.bounds.min_latitude == 36.0


class TestLoadConfigFromDict:
    """Tests for load_config_from_dict function."""

    def test_loads_minimal_config(self):
        """Loads config with minimal data."""
        data = {}

        with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
            result = load_config_from_dict(data)

        assert isinstance(result, Config)
        assert result.polling_interval_seconds == 60  # Default
        assert result.lookback_hours == 1  # Default

    def test_loads_full_config(self):
        """Loads complete configuration."""
        data = {
            "polling_interval_seconds": 120,
            "lookback_hours": 2,
            "points_of_interest": [
                {"name": "SF", "latitude": 37.7749, "longitude": -122.4194},
            ],
            "monitoring_regions": [
                {
                    "name": "Bay Area",
                    "bounds": {
                        "min_latitude": 36.0,
                        "max_latitude": 38.5,
                        "min_longitude": -123.0,
                        "max_longitude": -121.0,
                    },
                }
            ],
            "alert_channels": [
                {
                    "name": "test",
                    "type": "slack",
                    "webhook_url": "https://example.com/webhook",
                    "rules": {"min_magnitude": 3.0},
                }
            ],
            "firestore_database": "earthquake-alerts",
            "firestore_collection": "alerts",
            "min_fetch_magnitude": 2.0,
        }

        with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
            result = load_config_from_dict(data)

        assert result.polling_interval_seconds == 120
        assert result.lookback_hours == 2
        assert len(result.points_of_interest) == 1
        assert len(result.monitoring_regions) == 1
        assert len(result.alert_channels) == 1
        assert result.firestore_database == "earthquake-alerts"
        assert result.firestore_collection == "alerts"
        assert result.min_fetch_magnitude == 2.0

    def test_pois_referenced_in_channel_rules(self):
        """POIs defined at top level are available in channel rules."""
        data = {
            "points_of_interest": [
                {"name": "Office", "latitude": 37.5, "longitude": -122.0},
            ],
            "alert_channels": [
                {
                    "name": "test",
                    "type": "slack",
                    "webhook_url": "https://example.com",
                    "rules": {
                        "min_magnitude": 3.0,
                        "points_of_interest": ["Office"],
                    },
                }
            ],
        }

        with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
            result = load_config_from_dict(data)

        channel = result.alert_channels[0]
        assert len(channel.rules.points_of_interest) == 1
        assert channel.rules.points_of_interest[0].name == "Office"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_from_yaml_file(self):
        """Loads configuration from YAML file."""
        yaml_content = """
polling_interval_seconds: 300
lookback_hours: 3
monitoring_regions:
  - name: Test Region
    bounds:
      min_latitude: 35.0
      max_latitude: 40.0
      min_longitude: -125.0
      max_longitude: -120.0
alert_channels:
  - name: test-channel
    type: slack
    webhook_url: https://hooks.slack.com/test
    rules:
      min_magnitude: 2.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                result = load_config(temp_path)

            assert result.polling_interval_seconds == 300
            assert result.lookback_hours == 3
            assert len(result.monitoring_regions) == 1
            assert result.monitoring_regions[0].name == "Test Region"
            assert len(result.alert_channels) == 1
        finally:
            os.unlink(temp_path)

    def test_returns_default_config_when_file_not_found(self):
        """Returns default config when file doesn't exist."""
        with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
            result = load_config("/nonexistent/path/config.yaml")

        assert isinstance(result, Config)
        assert result.polling_interval_seconds == 60

    def test_returns_default_config_for_empty_file(self):
        """Returns default config when file is empty."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                result = load_config(temp_path)

            assert isinstance(result, Config)
        finally:
            os.unlink(temp_path)

    def test_uses_config_path_env_var(self):
        """Uses CONFIG_PATH environment variable when path not specified."""
        yaml_content = """
polling_interval_seconds: 180
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            with patch.dict(os.environ, {"CONFIG_PATH": temp_path}):
                with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                    result = load_config()

            assert result.polling_interval_seconds == 180
        finally:
            os.unlink(temp_path)


class TestLoadConfigFromEnv:
    """Tests for load_config_from_env function."""

    def test_returns_empty_config_without_webhook(self):
        """Returns empty config when no webhook URL available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SLACK_WEBHOOK_URL", None)
            os.environ.pop("GCP_PROJECT", None)
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                result = load_config_from_env()

        assert len(result.alert_channels) == 0

    def test_loads_config_from_env_vars(self):
        """Loads configuration from environment variables."""
        env_vars = {
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/T00/B00/XXX",
            "MONITORING_BOUNDS": "36.0,38.5,-123.0,-121.0",
            "MIN_MAGNITUDE": "3.5",
            "LOOKBACK_HOURS": "2",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                result = load_config_from_env()

        assert len(result.alert_channels) == 1
        assert result.alert_channels[0].webhook_url == "https://hooks.slack.com/services/T00/B00/XXX"
        assert result.alert_channels[0].rules.min_magnitude == 3.5
        assert result.lookback_hours == 2
        assert len(result.monitoring_regions) == 1
        assert result.monitoring_regions[0].bounds.min_latitude == 36.0

    def test_uses_secret_manager_when_available(self):
        """Uses Secret Manager for webhook when available."""
        mock_client = Mock()
        mock_client.get_secret.return_value = "https://secret-webhook.com"

        with patch.dict(os.environ, {"GCP_PROJECT": "test-project"}, clear=True):
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=mock_client):
                result = load_config_from_env()

        assert result.alert_channels[0].webhook_url == "https://secret-webhook.com"

    def test_falls_back_to_env_var_when_secret_not_found(self):
        """Falls back to env var when secret not found."""
        mock_client = Mock()
        mock_client.get_secret.return_value = None  # Secret not found

        env_vars = {
            "GCP_PROJECT": "test-project",
            "SLACK_WEBHOOK_URL": "https://env-webhook.com",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=mock_client):
                result = load_config_from_env()

        assert result.alert_channels[0].webhook_url == "https://env-webhook.com"

    def test_loads_firestore_database_from_env(self):
        """Loads Firestore database name from environment."""
        env_vars = {
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
            "FIRESTORE_DATABASE": "custom-database",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch('src.shell.config_loader._get_secret_manager_client', return_value=None):
                result = load_config_from_env()

        assert result.firestore_database == "custom-database"


class TestGetSecretManagerClient:
    """Tests for _get_secret_manager_client function."""

    def test_returns_none_without_project(self):
        """Returns None when GCP_PROJECT not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GCP_PROJECT", None)
            # Also mock gcloud command to fail
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = FileNotFoundError()
                result = _get_secret_manager_client()

        assert result is None

    def test_creates_client_with_project(self):
        """Creates client when GCP_PROJECT is set."""
        with patch.dict(os.environ, {"GCP_PROJECT": "test-project"}):
            with patch('src.shell.config_loader.SecretManagerClient') as MockClient:
                result = _get_secret_manager_client()

        MockClient.assert_called_once()
        assert result is not None

    def test_uses_gcloud_config_project(self):
        """Falls back to gcloud config for project ID."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GCP_PROJECT", None)
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "gcloud-project\n"

            with patch('subprocess.run', return_value=mock_result):
                with patch('src.shell.config_loader.SecretManagerClient') as MockClient:
                    result = _get_secret_manager_client()

        MockClient.assert_called_once()
        # Check that the project ID was extracted from gcloud
        call_args = MockClient.call_args
        assert call_args[0][0].project_id == "gcloud-project"
