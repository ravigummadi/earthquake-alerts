"""Deduplication logic - Pure functions.

This module handles logic for determining which earthquakes have already
been alerted on. All functions are pure with no side effects.

Note: The actual persistence of alerted IDs is handled by the imperative
shell (Firestore client). This module only contains the pure logic.
"""

from src.core.earthquake import Earthquake


def get_earthquake_ids(earthquakes: list[Earthquake]) -> set[str]:
    """Extract IDs from a list of earthquakes.

    Pure function.

    Args:
        earthquakes: List of earthquakes

    Returns:
        Set of earthquake IDs
    """
    return {e.id for e in earthquakes}


def get_new_earthquake_ids(
    earthquake_ids: set[str],
    already_alerted_ids: set[str],
) -> set[str]:
    """Determine which earthquake IDs are new (not yet alerted).

    Pure function.

    Args:
        earthquake_ids: All earthquake IDs from current fetch
        already_alerted_ids: IDs that have already been alerted

    Returns:
        Set of new earthquake IDs that haven't been alerted
    """
    return earthquake_ids - already_alerted_ids


def filter_already_alerted(
    earthquakes: list[Earthquake],
    already_alerted_ids: set[str],
) -> list[Earthquake]:
    """Filter out earthquakes that have already been alerted.

    Pure function.

    Args:
        earthquakes: List of earthquakes to filter
        already_alerted_ids: IDs that have already been alerted

    Returns:
        List of earthquakes that haven't been alerted yet
    """
    return [e for e in earthquakes if e.id not in already_alerted_ids]


def compute_ids_to_store(
    successfully_alerted: list[Earthquake],
) -> set[str]:
    """Compute which earthquake IDs should be stored as alerted.

    Pure function.

    Args:
        successfully_alerted: Earthquakes that were successfully alerted

    Returns:
        Set of IDs to mark as alerted
    """
    return {e.id for e in successfully_alerted}


def compute_ids_to_expire(
    stored_ids: set[str],
    current_earthquake_ids: set[str],
    max_stored: int = 1000,
) -> set[str]:
    """Compute which stored IDs can be expired.

    Pure function.

    We keep IDs that are still appearing in USGS data (to prevent re-alerting),
    and expire old ones when we exceed max_stored limit.

    Args:
        stored_ids: Currently stored earthquake IDs
        current_earthquake_ids: IDs from current USGS data
        max_stored: Maximum IDs to keep stored

    Returns:
        Set of IDs that can be removed from storage
    """
    # Never expire IDs that are in current data
    expirable = stored_ids - current_earthquake_ids

    # If we're under limit, don't expire anything
    if len(stored_ids) <= max_stored:
        return set()

    # Expire oldest IDs (we don't have timestamps, so just take excess)
    excess = len(stored_ids) - max_stored
    return set(list(expirable)[:excess])
