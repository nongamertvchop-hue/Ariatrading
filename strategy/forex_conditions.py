"""Forex-specific market condition and session guards.

This module enforces forex operational constraints before order routing:
1. Active session windows (e.g. London / New York high liquidity).
2. Rollover lockout (NY close 21:30 - 22:30 UTC) to guard against spread spikes.
3. Real-time spread thresholds against maximum allowable tolerance.

All evaluations are deterministic, fail-closed, and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class ForexSessionConfig:
    """Configurable trading hours and protection windows in UTC."""

    # Default sessions (UTC): London (07:00-16:00), New York (12:00-21:00)
    allowed_start_utc: time = time(7, 0)
    allowed_end_utc: time = time(21, 0)
    # Rollover window (UTC): 21:30 - 22:30 (spread spikes and liquidity drops)
    rollover_start_utc: time = time(21, 30)
    rollover_end_utc: time = time(22, 30)
    # Enforce trading session filter strictly
    enforce_session_filter: bool = True
    # Default maximum allowable spread in broker points
    default_max_spread_points: float = 25.0
    # Custom max spread points per symbol
    symbol_max_spread_points: Mapping[str, float] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.symbol_max_spread_points is None:
            object.__setattr__(self, "symbol_max_spread_points", {})
        if not isfinite(self.default_max_spread_points) or self.default_max_spread_points <= 0:
            raise ValueError("default_max_spread_points must be finite and > 0")


@dataclass(frozen=True)
class ForexConditionDecision:
    """Readiness decision based on Forex market conditions."""

    allowed: bool
    reason: str
    spread_points: float = 0.0
    max_spread_points: float = 0.0
    current_session: str = ""
    is_rollover: bool = False


def is_in_time_range(check_time: time, start: time, end: time) -> bool:
    """Return True if check_time is within start and end inclusive."""
    if start <= end:
        return start <= check_time <= end
    # Spanning midnight (e.g., 22:00 to 02:00)
    return check_time >= start or check_time <= end


def get_current_session(dt_utc: datetime) -> str:
    """Identify market session for a given UTC timestamp."""
    t = dt_utc.time()
    sessions = []
    # London: 07:00 - 16:00 UTC
    if is_in_time_range(t, time(7, 0), time(16, 0)):
        sessions.append("LONDON")
    # New York: 12:00 - 21:00 UTC
    if is_in_time_range(t, time(12, 0), time(21, 0)):
        sessions.append("NEW_YORK")
    # Tokyo/Asia: 00:00 - 09:00 UTC
    if is_in_time_range(t, time(0, 0), time(9, 0)):
        sessions.append("TOKYO")
    # Sydney: 21:00 - 06:00 UTC
    if is_in_time_range(t, time(21, 0), time(6, 0)):
        sessions.append("SYDNEY")

    return "+".join(sessions) if sessions else "OFF_HOURS"


def check_forex_conditions(
    *,
    symbol: str,
    bid: float,
    ask: float,
    point: float,
    timestamp: datetime,
    config: ForexSessionConfig | None = None,
) -> ForexConditionDecision:
    """Verify spread, rollover, and session rules before execution."""
    cfg = config or ForexSessionConfig()
    symbol = symbol.strip().upper()

    for name, val in [("bid", bid), ("ask", ask), ("point", point)]:
        if not isfinite(val) or val <= 0:
            return ForexConditionDecision(
                allowed=False,
                reason=f"{name} must be finite and > 0",
            )

    if ask < bid:
        return ForexConditionDecision(
            allowed=False,
            reason="crossed book: ask cannot be less than bid",
        )

    # Ensure UTC
    if timestamp.tzinfo is None:
        utc_dt = timestamp.replace(tzinfo=timezone.utc)
    else:
        utc_dt = timestamp.astimezone(timezone.utc)

    utc_time = utc_dt.time()
    session = get_current_session(utc_dt)

    # 1. Check Rollover window
    if is_in_time_range(utc_time, cfg.rollover_start_utc, cfg.rollover_end_utc):
        return ForexConditionDecision(
            allowed=False,
            reason=f"market is in rollover protection window ({cfg.rollover_start_utc.strftime('%H:%M')}-{cfg.rollover_end_utc.strftime('%H:%M')} UTC)",
            current_session=session,
            is_rollover=True,
        )

    # 2. Check Session window if enforced
    if cfg.enforce_session_filter:
        if not is_in_time_range(utc_time, cfg.allowed_start_utc, cfg.allowed_end_utc):
            return ForexConditionDecision(
                allowed=False,
                reason=f"outside allowed trading hours ({cfg.allowed_start_utc.strftime('%H:%M')}-{cfg.allowed_end_utc.strftime('%H:%M')} UTC)",
                current_session=session,
                is_rollover=False,
            )

    # 3. Check Spread
    spread_points = (ask - bid) / point
    max_spread = (
        cfg.symbol_max_spread_points.get(symbol, cfg.default_max_spread_points)
        if cfg.symbol_max_spread_points
        else cfg.default_max_spread_points
    )

    if spread_points > max_spread:
        return ForexConditionDecision(
            allowed=False,
            reason=f"spread {spread_points:.1f} pts exceeds maximum allowed {max_spread:.1f} pts",
            spread_points=spread_points,
            max_spread_points=max_spread,
            current_session=session,
            is_rollover=False,
        )

    return ForexConditionDecision(
        allowed=True,
        reason="forex market conditions passed",
        spread_points=spread_points,
        max_spread_points=max_spread,
        current_session=session,
        is_rollover=False,
    )
