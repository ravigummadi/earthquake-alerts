"""Tests for static map client.

Uses mocked tile fetching to avoid network calls in tests.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.core.static_map import MapConfig
from src.shell.static_map_client import StaticMapClient, MapImageResult


# Test map configuration
TEST_CONFIG = MapConfig(
    latitude=37.78,
    longitude=-122.42,
    zoom=10,
    width=400,
    height=300,
    marker_color="#dc2626",
    marker_radius=12,
)


class TestStaticMapClientInit:
    """Tests for StaticMapClient initialization."""

    def test_default_tile_url(self):
        """Default tile URL is OpenStreetMap."""
        client = StaticMapClient()
        assert "openstreetmap" in client.tile_url.lower()

    def test_custom_tile_url(self):
        """Custom tile URL is accepted."""
        custom_url = "https://tiles.example.com/{z}/{x}/{y}.png"
        client = StaticMapClient(tile_url=custom_url)
        assert client.tile_url == custom_url


class TestStaticMapClientGenerateMap:
    """Tests for StaticMapClient.generate_map()."""

    @patch("src.shell.static_map_client.StaticMap")
    def test_successful_generation_returns_image_bytes(self, mock_static_map_class):
        """Successful map generation returns PNG bytes."""
        # Set up mock
        mock_map = MagicMock()
        mock_static_map_class.return_value = mock_map

        # Mock the rendered image
        mock_image = MagicMock()
        mock_map.render.return_value = mock_image

        # Mock saving to bytes
        def save_to_buffer(buffer, format):
            buffer.write(b"PNG_IMAGE_DATA")

        mock_image.save = save_to_buffer

        client = StaticMapClient()
        result = client.generate_map(TEST_CONFIG)

        assert result.success is True
        assert result.image_bytes is not None
        assert len(result.image_bytes) > 0
        assert result.error is None

    @patch("src.shell.static_map_client.StaticMap")
    def test_adds_marker_at_coordinates(self, mock_static_map_class):
        """Marker is added at the earthquake coordinates."""
        mock_map = MagicMock()
        mock_static_map_class.return_value = mock_map
        mock_map.markers = []

        mock_image = MagicMock()
        mock_map.render.return_value = mock_image
        mock_image.save = lambda buf, format: buf.write(b"PNG")

        client = StaticMapClient()
        client.generate_map(TEST_CONFIG)

        # Check that add_marker was called
        assert mock_map.add_marker.called

    @patch("src.shell.static_map_client.StaticMap")
    def test_renders_at_specified_zoom(self, mock_static_map_class):
        """Map is rendered at the specified zoom level."""
        mock_map = MagicMock()
        mock_static_map_class.return_value = mock_map
        mock_map.markers = []

        mock_image = MagicMock()
        mock_map.render.return_value = mock_image
        mock_image.save = lambda buf, format: buf.write(b"PNG")

        client = StaticMapClient()
        client.generate_map(TEST_CONFIG)

        mock_map.render.assert_called_once_with(zoom=TEST_CONFIG.zoom)

    @patch("src.shell.static_map_client.StaticMap")
    def test_uses_specified_dimensions(self, mock_static_map_class):
        """Map uses the specified width and height."""
        mock_map = MagicMock()
        mock_static_map_class.return_value = mock_map
        mock_map.markers = []

        mock_image = MagicMock()
        mock_map.render.return_value = mock_image
        mock_image.save = lambda buf, format: buf.write(b"PNG")

        client = StaticMapClient()
        client.generate_map(TEST_CONFIG)

        mock_static_map_class.assert_called_once()
        call_args = mock_static_map_class.call_args
        assert call_args[0][0] == TEST_CONFIG.width
        assert call_args[0][1] == TEST_CONFIG.height

    @patch("src.shell.static_map_client.StaticMap")
    def test_exception_returns_failure(self, mock_static_map_class):
        """Exception during generation returns failure result."""
        mock_static_map_class.side_effect = Exception("Network error")

        client = StaticMapClient()
        result = client.generate_map(TEST_CONFIG)

        assert result.success is False
        assert result.image_bytes is None
        assert result.error is not None
        assert "Network error" in result.error


class TestMapImageResult:
    """Tests for MapImageResult dataclass."""

    def test_success_result(self):
        """Successful result has image bytes."""
        result = MapImageResult(
            success=True,
            image_bytes=b"PNG_DATA",
        )
        assert result.success is True
        assert result.image_bytes == b"PNG_DATA"
        assert result.error is None

    def test_failure_result(self):
        """Failure result has error message."""
        result = MapImageResult(
            success=False,
            error="Failed to fetch tiles",
        )
        assert result.success is False
        assert result.image_bytes is None
        assert result.error == "Failed to fetch tiles"
