"""Unit tests for deduplication logic.

Pure function tests - no mocks needed.
"""

import pytest
from datetime import datetime, timezone

from src.core.earthquake import Earthquake
from src.core.dedup import (
    get_earthquake_ids,
    get_new_earthquake_ids,
    filter_already_alerted,
    compute_ids_to_store,
    compute_ids_to_expire,
)


@pytest.fixture
def sample_earthquake():
    """Create a sample earthquake."""
    return Earthquake(
        id="eq1",
        magnitude=4.0,
        place="Test Location",
        time=datetime.now(timezone.utc),
        latitude=37.77,
        longitude=-122.42,
        depth_km=10.0,
        url="https://example.com",
    )


@pytest.fixture
def earthquakes(sample_earthquake):
    """Create list of earthquakes."""
    return [
        sample_earthquake,
        Earthquake(**{**sample_earthquake.__dict__, "id": "eq2"}),
        Earthquake(**{**sample_earthquake.__dict__, "id": "eq3"}),
    ]


class TestGetEarthquakeIds:
    """Tests for get_earthquake_ids() function."""

    def test_extracts_ids(self, earthquakes):
        """Should extract all earthquake IDs."""
        result = get_earthquake_ids(earthquakes)
        assert result == {"eq1", "eq2", "eq3"}

    def test_empty_list(self):
        """Should return empty set for empty list."""
        result = get_earthquake_ids([])
        assert result == set()


class TestGetNewEarthquakeIds:
    """Tests for get_new_earthquake_ids() function."""

    def test_finds_new_ids(self):
        """Should find IDs not in already_alerted set."""
        current = {"eq1", "eq2", "eq3"}
        already_alerted = {"eq1"}

        result = get_new_earthquake_ids(current, already_alerted)

        assert result == {"eq2", "eq3"}

    def test_all_new(self):
        """Should return all IDs when none alerted."""
        current = {"eq1", "eq2"}
        already_alerted = set()

        result = get_new_earthquake_ids(current, already_alerted)

        assert result == {"eq1", "eq2"}

    def test_none_new(self):
        """Should return empty set when all alerted."""
        current = {"eq1", "eq2"}
        already_alerted = {"eq1", "eq2", "eq3"}

        result = get_new_earthquake_ids(current, already_alerted)

        assert result == set()


class TestFilterAlreadyAlerted:
    """Tests for filter_already_alerted() function."""

    def test_filters_alerted(self, earthquakes):
        """Should remove already-alerted earthquakes."""
        already_alerted = {"eq1", "eq3"}

        result = filter_already_alerted(earthquakes, already_alerted)

        assert len(result) == 1
        assert result[0].id == "eq2"

    def test_all_new(self, earthquakes):
        """Should return all when none alerted."""
        result = filter_already_alerted(earthquakes, set())
        assert len(result) == 3

    def test_all_alerted(self, earthquakes):
        """Should return empty when all alerted."""
        already_alerted = {"eq1", "eq2", "eq3"}
        result = filter_already_alerted(earthquakes, already_alerted)
        assert len(result) == 0


class TestComputeIdsToStore:
    """Tests for compute_ids_to_store() function."""

    def test_returns_ids_from_earthquakes(self, earthquakes):
        """Should return IDs of successfully alerted earthquakes."""
        result = compute_ids_to_store(earthquakes)
        assert result == {"eq1", "eq2", "eq3"}

    def test_empty_list(self):
        """Should return empty set for empty list."""
        result = compute_ids_to_store([])
        assert result == set()


class TestComputeIdsToExpire:
    """Tests for compute_ids_to_expire() function."""

    def test_keeps_current_ids(self):
        """Should never expire IDs that are in current data."""
        stored = {"eq1", "eq2", "eq3", "eq4", "eq5"}
        current = {"eq1", "eq2"}

        result = compute_ids_to_expire(stored, current, max_stored=3)

        # eq1 and eq2 should NOT be in the expired set
        assert "eq1" not in result
        assert "eq2" not in result

    def test_expires_when_over_limit(self):
        """Should expire old IDs when over limit."""
        stored = {"eq1", "eq2", "eq3", "eq4", "eq5"}
        current = {"eq1"}  # Only eq1 is current

        result = compute_ids_to_expire(stored, current, max_stored=3)

        # Should expire 2 IDs (5 stored - 3 max = 2 to expire)
        assert len(result) == 2
        # Should not expire eq1 (still current)
        assert "eq1" not in result

    def test_no_expire_when_under_limit(self):
        """Should not expire anything when under limit."""
        stored = {"eq1", "eq2", "eq3"}
        current = {"eq1"}

        result = compute_ids_to_expire(stored, current, max_stored=100)

        assert result == set()

    def test_no_expire_at_limit(self):
        """Should not expire when exactly at limit."""
        stored = {"eq1", "eq2", "eq3"}
        current = set()

        result = compute_ids_to_expire(stored, current, max_stored=3)

        assert result == set()


class TestRepeatedIdsEdgeCases:
    """Edge cases for deduplication with repeated IDs and boundary conditions."""

    def test_get_earthquake_ids_deduplicates_repeated_instances(self, sample_earthquake):
        """get_earthquake_ids returns unique set even if earthquake list has duplicates."""
        eq1 = sample_earthquake
        eq2 = Earthquake(**{**sample_earthquake.__dict__, "id": "eq2"})
        earthquake_list = [eq1, eq1, eq2, eq1, eq2]

        result = get_earthquake_ids(earthquake_list)
        assert result == {"eq1", "eq2"}

    def test_filter_already_alerted_drops_all_duplicates_of_alerted_id(self, sample_earthquake):
        """filter_already_alerted eliminates every duplicate instance of an alerted ID."""
        eq1 = sample_earthquake  # id="eq1"
        eq2 = Earthquake(**{**sample_earthquake.__dict__, "id": "eq2"})
        earthquake_list = [eq1, eq1, eq2, eq1]

        result = filter_already_alerted(earthquake_list, {"eq1"})
        assert len(result) == 1
        assert result[0].id == "eq2"

    def test_filter_already_alerted_retains_duplicates_if_not_alerted(self, sample_earthquake):
        """filter_already_alerted retains all items if ID is not yet alerted."""
        eq1 = sample_earthquake
        earthquake_list = [eq1, eq1]

        result = filter_already_alerted(earthquake_list, set())
        assert len(result) == 2
        assert result[0].id == "eq1"
        assert result[1].id == "eq1"

    def test_compute_ids_to_store_deduplicates_repeated_earthquakes(self, sample_earthquake):
        """compute_ids_to_store collapses repeated earthquakes into a single set of IDs."""
        eq1 = sample_earthquake
        eq2 = Earthquake(**{**sample_earthquake.__dict__, "id": "eq2"})
        result = compute_ids_to_store([eq1, eq1, eq2, eq2, eq1])
        assert result == {"eq1", "eq2"}

    def test_compute_ids_to_expire_never_expires_current_even_over_limit(self):
        """Current earthquake IDs are never expired, even if stored count exceeds max_stored."""
        stored = {"eq1", "eq2", "eq3", "eq4"}
        current = {"eq1", "eq2", "eq3", "eq4"}
        result = compute_ids_to_expire(stored, current, max_stored=2)
        assert result == set()

    def test_compute_ids_to_expire_excess_greater_than_available_expirables(self):
        """Handles scenario where excess count exceeds the number of non-current IDs."""
        stored = {"eq1", "eq2", "eq3", "eq4", "eq5"}
        current = {"eq1", "eq2", "eq3", "eq4"}  # Only eq5 is expirable
        # max_stored=2 -> excess = 5 - 2 = 3. Only 1 ID is expirable.
        result = compute_ids_to_expire(stored, current, max_stored=2)
        assert result == {"eq5"}

    def test_compute_ids_to_expire_zero_max_stored(self):
        """max_stored=0 expires all expirable IDs."""
        stored = {"eq1", "eq2"}
        current = set()
        result = compute_ids_to_expire(stored, current, max_stored=0)
        assert result == {"eq1", "eq2"}

    def test_compute_ids_to_expire_empty_stored(self):
        """Empty stored set returns empty set."""
        result = compute_ids_to_expire(set(), {"eq1"}, max_stored=10)
        assert result == set()
