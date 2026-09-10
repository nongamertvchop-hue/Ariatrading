"""Runtime safety controls for the MT5 execution boundary.

These controls are intentionally independent from strategy generation. They make
unsafe runtime state fail closed before an order can be submitted.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SUPPORTED_TIMEFRAMES = frozenset({"1m", "5m", "15m", "30m", "1h", "4h", "1D"})


@dataclass(frozen=True)
class RuntimeSafetyConfig:
    """Validated operational configuration; values are not strategy parameters."""

    max_tick_age_seconds: float = 10.0
    max_spread_points: float = 30.0
    max_daily_drawdown_fraction: float = 0.02
    max_positions: int = 5
    max_positions_per_symbol: int = 1
    max_clock_skew_seconds: float = 5.0

    def validate(self) -> None:
        finite_positive = (
            self.max_tick_age_seconds,
            self.max_spread_points,
            self.max_clock_skew_seconds,
        )
        if not all(math.isfinite(v) and v > 0 for v in finite_positive):
            raise ValueError("runtime time/spread limits must be finite and > 0")
        if not math.isfinite(self.max_daily_drawdown_fraction) or not 0 < self.max_daily_drawdown_fraction < 1:
            raise ValueError("max_daily_drawdown_fraction must be between 0 and 1")
        if self.max_positions < 1 or self.max_positions_per_symbol < 1:
            raise ValueError("position limits must be >= 1")
        if self.max_positions_per_symbol > self.max_positions:
            raise ValueError("per-symbol position limit cannot exceed global position limit")


def validate_runtime_configuration(*, timeframe: str, symbols: Iterable[str], config: RuntimeSafetyConfig) -> tuple[str, ...]:
    """Validate static configuration before connecting to a broker."""
    normalized_timeframe = timeframe.strip()
    if normalized_timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    normalized_symbols = tuple(sorted({s.strip().upper() for s in symbols if s.strip()}))
    if not normalized_symbols:
        raise ValueError("at least one symbol is required")
    config.validate()
    return normalized_symbols


def check_clock_skew(broker_time: datetime, now: datetime, max_skew_seconds: float) -> tuple[bool, str]:
    """Reject timestamps that are too far ahead/behind the local clock."""
    if broker_time.tzinfo is None or now.tzinfo is None:
        raise ValueError("clock timestamps must be timezone-aware")
    skew = abs((now.astimezone(timezone.utc) - broker_time.astimezone(timezone.utc)).total_seconds())
    if skew > max_skew_seconds:
        return False, f"broker/local clock skew {skew:.3f}s exceeds {max_skew_seconds:.3f}s"
    return True, "clock skew within limit"


def exposure_counts(positions: Iterable[object]) -> tuple[int, dict[str, int]]:
    """Count owned positions globally and per symbol."""
    per_symbol: dict[str, int] = {}
    total = 0
    for position in positions:
        symbol = str(getattr(position, "symbol", "")).strip().upper()
        if not symbol:
            continue
        per_symbol[symbol] = per_symbol.get(symbol, 0) + 1
        total += 1
    return total, per_symbol


class KillSwitch:
    """Durable operator kill switch.

    Presence of the file means: do not create new entries. Deleting the file is
    an explicit operator action. Existing positions are never force-closed here.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def engaged(self) -> bool:
        return self.path.exists()

    def engage(self, reason: str = "operator requested stop") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "engaged_at": datetime.now(timezone.utc).isoformat(),
            "reason": str(reason),
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def release(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return

    def check(self) -> tuple[bool, str]:
        if self.engaged():
            return False, "kill switch engaged; new entries disabled"
        return True, "kill switch clear"
