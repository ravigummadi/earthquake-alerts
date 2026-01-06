"""Tests for rate limiting logic."""

import pytest

from src.core.config import RateLimitConfig
from src.core.rate_limit import (
    RateLimitState,
    check_rate_limit,
    record_alert,
    get_violations,
    format_violation_message,
)


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    def test_allows_alert_under_limits(self):
        """Alert is allowed when under all limits."""
        state = RateLimitState(total_alerts=0)
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        result = check_rate_limit("test-channel", state, config)

        assert result.allowed is True
        assert result.reason is None

    def test_blocks_alert_when_global_limit_reached(self):
        """Alert is blocked when global limit is reached."""
        state = RateLimitState(total_alerts=10)
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        result = check_rate_limit("test-channel", state, config)

        assert result.allowed is False
        assert "Global limit exceeded" in result.reason
        assert "10/10" in result.reason

    def test_blocks_alert_when_channel_limit_reached(self):
        """Alert is blocked when channel limit is reached."""
        state = RateLimitState(
            total_alerts=3,
            alerts_per_channel={"test-channel": 5},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        result = check_rate_limit("test-channel", state, config)

        assert result.allowed is False
        assert "Channel limit exceeded" in result.reason
        assert "test-channel" in result.reason

    def test_allows_different_channel_when_one_is_limited(self):
        """Different channel is allowed when another is at limit."""
        state = RateLimitState(
            total_alerts=3,
            alerts_per_channel={"limited-channel": 5},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        result = check_rate_limit("other-channel", state, config)

        assert result.allowed is True

    def test_unlimited_when_max_is_zero(self):
        """No limit applied when max is set to 0 (unlimited)."""
        state = RateLimitState(total_alerts=1000)
        config = RateLimitConfig(max_alerts_per_run=0, max_alerts_per_channel=0)

        result = check_rate_limit("test-channel", state, config)

        assert result.allowed is True

    def test_returns_current_counts(self):
        """Result includes current alert counts."""
        state = RateLimitState(
            total_alerts=5,
            alerts_per_channel={"test-channel": 3},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        result = check_rate_limit("test-channel", state, config)

        assert result.total_count == 5
        assert result.channel_count == 3


class TestRecordAlert:
    """Tests for record_alert function."""

    def test_increments_total_count(self):
        """Recording an alert increments total count."""
        state = RateLimitState(total_alerts=5)

        new_state = record_alert("test-channel", state)

        assert new_state.total_alerts == 6

    def test_increments_channel_count(self):
        """Recording an alert increments channel count."""
        state = RateLimitState(
            total_alerts=5,
            alerts_per_channel={"test-channel": 2},
        )

        new_state = record_alert("test-channel", state)

        assert new_state.alerts_per_channel["test-channel"] == 3

    def test_creates_channel_entry_if_missing(self):
        """Recording creates channel entry if not exists."""
        state = RateLimitState(total_alerts=5)

        new_state = record_alert("new-channel", state)

        assert new_state.alerts_per_channel["new-channel"] == 1

    def test_does_not_modify_original_state(self):
        """Recording returns new state, doesn't modify original."""
        original = RateLimitState(
            total_alerts=5,
            alerts_per_channel={"test-channel": 2},
        )

        new_state = record_alert("test-channel", original)

        # Original should be unchanged
        assert original.total_alerts == 5
        assert original.alerts_per_channel["test-channel"] == 2
        # New state should be different
        assert new_state is not original


class TestGetViolations:
    """Tests for get_violations function."""

    def test_returns_empty_when_under_limits(self):
        """No violations when under all limits."""
        state = RateLimitState(total_alerts=5)
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        violations = get_violations(state, config)

        assert violations == []

    def test_detects_global_limit_violation(self):
        """Detects when global limit is reached."""
        state = RateLimitState(total_alerts=10)
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        violations = get_violations(state, config)

        assert len(violations) == 1
        assert violations[0].limit_type == "global"
        assert violations[0].current_count == 10
        assert violations[0].max_allowed == 10

    def test_detects_channel_limit_violation(self):
        """Detects when channel limit is reached."""
        state = RateLimitState(
            total_alerts=5,
            alerts_per_channel={"test-channel": 5},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        violations = get_violations(state, config)

        assert len(violations) == 1
        assert violations[0].limit_type == "channel"
        assert violations[0].channel_name == "test-channel"

    def test_detects_multiple_violations(self):
        """Detects multiple violations at once."""
        state = RateLimitState(
            total_alerts=10,
            alerts_per_channel={"channel-a": 5, "channel-b": 5},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)

        violations = get_violations(state, config)

        # Should have global + 2 channel violations
        assert len(violations) == 3

    def test_no_violations_when_unlimited(self):
        """No violations when limits are disabled (0)."""
        state = RateLimitState(
            total_alerts=1000,
            alerts_per_channel={"test-channel": 500},
        )
        config = RateLimitConfig(max_alerts_per_run=0, max_alerts_per_channel=0)

        violations = get_violations(state, config)

        assert violations == []


class TestFormatViolationMessage:
    """Tests for format_violation_message function."""

    def test_returns_empty_for_no_violations(self):
        """Returns empty string when no violations."""
        message = format_violation_message([])

        assert message == ""

    def test_formats_single_violation(self):
        """Formats a single violation correctly."""
        state = RateLimitState(total_alerts=10)
        config = RateLimitConfig(max_alerts_per_run=10)
        violations = get_violations(state, config)

        message = format_violation_message(violations)

        assert "Rate limit violations detected" in message
        assert "Global rate limit reached" in message

    def test_formats_multiple_violations(self):
        """Formats multiple violations correctly."""
        state = RateLimitState(
            total_alerts=10,
            alerts_per_channel={"channel-a": 5},
        )
        config = RateLimitConfig(max_alerts_per_run=10, max_alerts_per_channel=5)
        violations = get_violations(state, config)

        message = format_violation_message(violations)

        assert "Rate limit violations detected" in message
        assert "Global rate limit reached" in message
        assert "channel-a" in message
