"""Rate limiting logic - Pure functions.

This module handles rate limiting for alert notifications to prevent
spam and detect anomalies. All functions are pure with no side effects.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import RateLimitConfig


@dataclass
class RateLimitState:
    """Tracks alert counts during a monitoring cycle.

    Attributes:
        total_alerts: Total alerts sent this cycle
        alerts_per_channel: Count of alerts sent to each channel
    """
    total_alerts: int = 0
    alerts_per_channel: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RateLimitResult:
    """Result of checking rate limits.

    Attributes:
        allowed: Whether the alert is allowed
        reason: Reason if not allowed (None if allowed)
        total_count: Current total alert count
        channel_count: Current channel alert count
    """
    allowed: bool
    reason: str | None
    total_count: int
    channel_count: int


@dataclass(frozen=True)
class RateLimitViolation:
    """Represents a rate limit violation.

    Attributes:
        channel_name: Channel that hit the limit (None for global limit)
        limit_type: Type of limit violated ('global' or 'channel')
        current_count: Current count when limit was hit
        max_allowed: Maximum allowed count
        message: Human-readable description
    """
    channel_name: str | None
    limit_type: str
    current_count: int
    max_allowed: int
    message: str


def check_rate_limit(
    channel_name: str,
    state: RateLimitState,
    config: "RateLimitConfig",
) -> RateLimitResult:
    """Check if an alert is allowed under rate limits.

    Pure function.

    Args:
        channel_name: Name of the channel to send to
        state: Current rate limit state
        config: Rate limit configuration

    Returns:
        RateLimitResult indicating if alert is allowed
    """
    channel_count = state.alerts_per_channel.get(channel_name, 0)

    # Check global limit
    if config.max_alerts_per_run > 0:
        if state.total_alerts >= config.max_alerts_per_run:
            return RateLimitResult(
                allowed=False,
                reason=f"Global limit exceeded: {state.total_alerts}/{config.max_alerts_per_run} alerts",
                total_count=state.total_alerts,
                channel_count=channel_count,
            )

    # Check per-channel limit
    if config.max_alerts_per_channel > 0:
        if channel_count >= config.max_alerts_per_channel:
            return RateLimitResult(
                allowed=False,
                reason=f"Channel limit exceeded for '{channel_name}': {channel_count}/{config.max_alerts_per_channel} alerts",
                total_count=state.total_alerts,
                channel_count=channel_count,
            )

    return RateLimitResult(
        allowed=True,
        reason=None,
        total_count=state.total_alerts,
        channel_count=channel_count,
    )


def record_alert(
    channel_name: str,
    state: RateLimitState,
) -> RateLimitState:
    """Record an alert and return updated state.

    Pure function - returns new state without modifying input.

    Args:
        channel_name: Name of the channel alert was sent to
        state: Current rate limit state

    Returns:
        New state with incremented counts
    """
    new_channel_counts = dict(state.alerts_per_channel)
    new_channel_counts[channel_name] = new_channel_counts.get(channel_name, 0) + 1

    return RateLimitState(
        total_alerts=state.total_alerts + 1,
        alerts_per_channel=new_channel_counts,
    )


def get_violations(
    state: RateLimitState,
    config: "RateLimitConfig",
) -> list[RateLimitViolation]:
    """Get all rate limit violations from the current state.

    Pure function.

    Args:
        state: Current rate limit state
        config: Rate limit configuration

    Returns:
        List of violations (empty if none)
    """
    violations = []

    # Check global limit
    if config.max_alerts_per_run > 0:
        if state.total_alerts >= config.max_alerts_per_run:
            violations.append(RateLimitViolation(
                channel_name=None,
                limit_type="global",
                current_count=state.total_alerts,
                max_allowed=config.max_alerts_per_run,
                message=f"Global rate limit reached: {state.total_alerts}/{config.max_alerts_per_run} alerts",
            ))

    # Check per-channel limits
    if config.max_alerts_per_channel > 0:
        for channel_name, count in state.alerts_per_channel.items():
            if count >= config.max_alerts_per_channel:
                violations.append(RateLimitViolation(
                    channel_name=channel_name,
                    limit_type="channel",
                    current_count=count,
                    max_allowed=config.max_alerts_per_channel,
                    message=f"Channel '{channel_name}' rate limit reached: {count}/{config.max_alerts_per_channel} alerts",
                ))

    return violations


def format_violation_message(violations: list[RateLimitViolation]) -> str:
    """Format violations into a human-readable message.

    Pure function.

    Args:
        violations: List of rate limit violations

    Returns:
        Formatted message string
    """
    if not violations:
        return ""

    lines = ["Rate limit violations detected:"]
    for v in violations:
        lines.append(f"  - {v.message}")

    return "\n".join(lines)
