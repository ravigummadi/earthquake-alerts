"""Cloud Function Entry Point - Root Module.

This is the root-level entry point for Google Cloud Functions.
It imports from the src package.
"""

from src.main import (
    earthquake_monitor,
    earthquake_monitor_pubsub,
)

__all__ = [
    "earthquake_monitor",
    "earthquake_monitor_pubsub",
]
