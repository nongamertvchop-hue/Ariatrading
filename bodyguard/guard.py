"""Fail-closed safety checks for Ariatrading execution orchestration.

This module is intentionally side-effect free: it never talks to a broker and
cannot place an order. A caller must receive an explicit ``allowed`` decision
before it can continue with its own demo/paper execution path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

ALLOWED_MODES = frozenset({"DEMO", "PAPER", "ALERT_ONLY"})
ALLOWED_DIRECTIONS = frozenset({"LONG", "SHORT"})


@dataclass(frozen=True)
class BodyguardConfig:
    """Conservative limits for the safety boundary."""

    max_lot_size: float = 1.0
    max_signal_age: timedelta = timedelta(minutes=5)
    allowed_symbols: frozenset[str] | None = None


@dataclass(frozen=True)
class SafetyRequest:
    """Immutable request data presented to Bodyguard before execution."""

    mode: str
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    lot_size: float
    signal_time: datetime


@dataclass(frozen=True)
class SafetyDecision:
    """Auditable allow/deny result."""

    allowed: bool
    reason: str


class Bodyguard:
    """Fail-closed validator for execution-bound requests."""

    def __init__(self, config: BodyguardConfig | None = None) -> None:
        self.config = config or BodyguardConfig()
        self._validate_config()

    def check(self, request: SafetyRequest, *, now: datetime | None = None) -> SafetyDecision:
        """Validate a request without performing any external side effects."""
        try:
            mode = request.mode.strip().upper()
            symbol = request.symbol.strip().upper()
            direction = request.direction.strip().upper()
        except AttributeError:
            return SafetyDecision(False, "invalid request text fields")

        if mode not in ALLOWED_MODES:
            return SafetyDecision(False, "execution mode is not permitted by Bodyguard")
        if not symbol:
            return SafetyDecision(False, "symbol is required")
        if direction not in ALLOWED_DIRECTIONS:
            return SafetyDecision(False, "direction is invalid")
        if self.config.allowed_symbols is not None and symbol not in self.config.allowed_symbols:
            return SafetyDecision(False, "symbol is not allowlisted")

        numeric_values = (request.entry, request.stop_loss, request.lot_size)
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in numeric_values):
            return SafetyDecision(False, "entry, stop loss, and lot size must be finite numbers")
        if request.entry <= 0 or request.stop_loss <= 0:
            return SafetyDecision(False, "entry and stop loss must be positive")
        if request.lot_size <= 0:
            return SafetyDecision(False, "lot size must be positive")
        if request.lot_size > self.config.max_lot_size:
            return SafetyDecision(False, "lot size exceeds Bodyguard limit")

        if direction == "LONG" and request.stop_loss >= request.entry:
            return SafetyDecision(False, "LONG stop loss must be below entry")
        if direction == "SHORT" and request.stop_loss <= request.entry:
            return SafetyDecision(False, "SHORT stop loss must be above entry")

        if request.signal_time.tzinfo is None:
            return SafetyDecision(False, "signal time must be timezone-aware")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            return SafetyDecision(False, "current time must be timezone-aware")
        age = current_time - request.signal_time.astimezone(timezone.utc)
        if age < timedelta(0):
            return SafetyDecision(False, "signal time is in the future")
        if age > self.config.max_signal_age:
            return SafetyDecision(False, "signal is stale")

        return SafetyDecision(True, "request passed Bodyguard checks")

    def _validate_config(self) -> None:
        if not math.isfinite(self.config.max_lot_size) or self.config.max_lot_size <= 0:
            raise ValueError("max_lot_size must be a positive finite number")
        if self.config.max_signal_age <= timedelta(0):
            raise ValueError("max_signal_age must be positive")
        if self.config.allowed_symbols is not None:
            normalized = frozenset(symbol.strip().upper() for symbol in self.config.allowed_symbols)
            if not normalized or any(not symbol for symbol in normalized):
                raise ValueError("allowed_symbols must contain non-empty symbols")
            object.__setattr__(self.config, "allowed_symbols", normalized)
