"""Functional Core - Pure functions with no side effects.

This module contains all business logic as pure functions:
- Earthquake data parsing
- Geo/distance calculations
- Alert rule evaluation
- Message formatting
- Deduplication logic

All functions here are deterministic and have no I/O.
"""

from src.core.earthquake import Earthquake, parse_earthquakes
from src.core.geo import calculate_distance, is_within_bounds, is_within_radius
from src.core.rules import AlertRule, evaluate_rules, filter_earthquakes_by_rules
from src.core.formatter import format_slack_message, format_earthquake_summary
from src.core.dedup import get_new_earthquake_ids, filter_already_alerted

__all__ = [
    # Earthquake
    "Earthquake",
    "parse_earthquakes",
    # Geo
    "calculate_distance",
    "is_within_bounds",
    "is_within_radius",
    # Rules
    "AlertRule",
    "evaluate_rules",
    "filter_earthquakes_by_rules",
    # Formatter
    "format_slack_message",
    "format_earthquake_summary",
    # Dedup
    "get_new_earthquake_ids",
    "filter_already_alerted",
]
