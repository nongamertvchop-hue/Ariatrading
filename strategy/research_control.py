"""Reproducible research-control metadata for Ariatrading.

The control plane records immutable experiment configuration and a deterministic
fingerprint of the exact candle payload supplied to a research run. It does not
change strategy decisions, optimize parameters, or connect to a broker.
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime, time
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class ResearchConfig:
    """Immutable configuration needed to reproduce one historical experiment."""

    symbol: str
    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    reward_risk: float = 2.0
    max_hold_bars: int = 20
    entry_timing: str = "signal_reference"

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must be non-empty")
        if not self.timeframe or not self.timeframe.strip():
            raise ValueError("timeframe must be non-empty")
        if self.history_bars < 1:
            raise ValueError("history_bars must be >= 1")
        if self.test_bars < 1:
            raise ValueError("test_bars must be >= 1")
        if self.step_bars < self.test_bars:
            raise ValueError("step_bars must be >= test_bars")
        if self.reward_risk <= 0:
            raise ValueError("reward_risk must be > 0")
        if self.max_hold_bars < 1:
            raise ValueError("max_hold_bars must be >= 1")
        if not self.entry_timing or not self.entry_timing.strip():
            raise ValueError("entry_timing must be non-empty")


@dataclass(frozen=True)
class DatasetFingerprint:
    """Stable SHA-256 fingerprint of a canonical candle sequence."""

    sha256: str
    candle_count: int
    first_time: str | None
    last_time: str | None


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, dict):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported dataset value type: {type(value).__name__}")


def fingerprint_candles(candles: list[dict]) -> DatasetFingerprint:
    """Hash candles without mutating them or relying on dictionary insertion order."""
    canonical = [_canonical_value(candle) for candle in candles]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    times = [candle.get("time") for candle in candles if candle.get("time") is not None]
    normalized_times = [_canonical_value(value) for value in times]
    return DatasetFingerprint(
        sha256=digest,
        candle_count=len(candles),
        first_time=normalized_times[0] if normalized_times else None,
        last_time=normalized_times[-1] if normalized_times else None,
    )


def config_fingerprint(config: ResearchConfig) -> str:
    """Return a stable SHA-256 fingerprint for an experiment configuration."""
    payload = json.dumps(asdict(config), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchRun:
    """Identifiers that make a research result traceable and reproducible."""

    config: ResearchConfig
    config_sha256: str
    dataset: DatasetFingerprint


def build_research_run(config: ResearchConfig, candles: list[dict]) -> ResearchRun:
    """Bind configuration and dataset fingerprints into one immutable run record."""
    return ResearchRun(
        config=config,
        config_sha256=config_fingerprint(config),
        dataset=fingerprint_candles(candles),
    )


__all__ = [
    "DatasetFingerprint",
    "ResearchConfig",
    "ResearchRun",
    "build_research_run",
    "config_fingerprint",
    "fingerprint_candles",
]
