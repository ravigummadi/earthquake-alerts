"""Static Map Client - Imperative Shell.

This module handles generating static map images using OpenStreetMap tiles.
All I/O is contained here; map configuration is in the core module.
"""

import io
import logging
from dataclasses import dataclass

from staticmap import StaticMap, CircleMarker

from src.core.static_map import MapConfig


logger = logging.getLogger(__name__)


@dataclass
class MapImageResult:
    """Result of map image generation.

    Attributes:
        success: Whether the image was generated successfully
        image_bytes: PNG image data if successful
        error: Error message if failed
    """
    success: bool
    image_bytes: bytes | None = None
    error: str | None = None


class StaticMapClient:
    """Client for generating static map images.

    This is part of the imperative shell - it handles I/O (fetching map tiles
    and rendering images).
    """

    def __init__(self, tile_url: str | None = None) -> None:
        """Initialize static map client.

        Args:
            tile_url: Custom tile URL template. Defaults to OpenStreetMap.
        """
        # Default to OpenStreetMap tiles
        self.tile_url = tile_url or "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    def generate_map(self, config: MapConfig) -> MapImageResult:
        """Generate a static map image for an earthquake.

        This method performs I/O (fetches map tiles from tile server).

        Args:
            config: Map configuration from core module

        Returns:
            MapImageResult with image bytes or error
        """
        logger.info(
            "Generating static map for (%.4f, %.4f) at zoom %d",
            config.latitude,
            config.longitude,
            config.zoom,
        )

        try:
            # Create static map with specified dimensions
            static_map = StaticMap(
                config.width,
                config.height,
                url_template=self.tile_url,
            )

            # Parse hex color to RGB tuple
            color = self._hex_to_rgb(config.marker_color)

            # Add epicenter marker
            marker = CircleMarker(
                (config.longitude, config.latitude),  # (lon, lat) order for staticmap
                color,
                config.marker_radius,
            )
            static_map.add_marker(marker)

            # Add outer ring for visibility (white border effect)
            outer_marker = CircleMarker(
                (config.longitude, config.latitude),
                "white",
                config.marker_radius + 3,
            )
            # Insert outer marker before inner marker so it renders behind
            static_map.markers.insert(0, outer_marker)

            # Render the map centered on the earthquake location
            image = static_map.render(zoom=config.zoom)

            # Convert to PNG bytes
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            logger.info(
                "Generated map image: %d bytes",
                len(image_bytes),
            )

            return MapImageResult(
                success=True,
                image_bytes=image_bytes,
            )

        except Exception as e:
            logger.error("Failed to generate map: %s", str(e))
            return MapImageResult(
                success=False,
                error=str(e),
            )

    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to staticmap color format.

        Args:
            hex_color: Hex color string (e.g., "#dc2626")

        Returns:
            Color string for staticmap (keeps hex format, staticmap supports it)
        """
        # staticmap accepts hex colors directly
        return hex_color
