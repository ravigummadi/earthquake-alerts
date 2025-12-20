"""Imperative Shell - I/O and side effects.

This module contains all code that interacts with external systems:
- USGS API client (HTTP)
- Slack webhook client (HTTP)
- Firestore client (database)
- Configuration loading (environment/files)

Keep this layer thin and simple. All business logic should be in core.
"""

from src.shell.usgs_client import USGSClient
from src.shell.slack_client import SlackClient
from src.shell.firestore_client import FirestoreClient
from src.shell.config_loader import load_config, Config

__all__ = [
    "USGSClient",
    "SlackClient",
    "FirestoreClient",
    "load_config",
    "Config",
]
