"""Validated multi-timeframe walk-forward research orchestration.

The runner is deliberately thin: it validates each supplied OHLC stream with
feed-integrity checks, runs the existing chronological walk-forward engine, and
builds the descriptive cross-timeframe report. It does not optimize parameters,
rank a winner, or alter strategy decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .execution import ExecutionModel
from .feed_integrity import FeedIntegrityReport, validate_feed_batch
from .multitimeframe_report import MultiTimeframeReport, build_multitimeframe_report
from .timeframe import SUPPORTED_TIMEFRAMES
from .walk_forward import WalkForwardResult, walk_forward_backtest


@dataclass(frozen=True)
class TimeframeResearchInput:
    timeframe: str
    bars: int
    integrity: FeedIntegrityReport


@dataclass(frozen=True)
class MultiTimeframeResearchResult:
    report: MultiTimeframeReport
    results: dict[str, WalkForwardResult]
    inputs: tuple[TimeframeResearchInput, ...]


class _FeedBar:
    __slots__ = ("time", "open", "high", "low", "close")

    def __init__(self, raw: dict, timeframe: str) -> None:
        timestamp = raw.get("time")
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(
                f"research candles for {timeframe} require timezone-aware datetime 'time'"
            )
        try:
            self.time = timestamp
            self.open = float(raw["open"])
            self.high = float(raw["high"])
            self.low = float(raw["low"])
            self.close = float(raw["close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"research candle for {timeframe} has invalid OHLC fields") from exc


def _validate_mapping_keys(
    candles_by_timeframe: Mapping[str, list[dict]],
    expected_timeframes: tuple[str, ...],
) -> None:
    actual = set(candles_by_timeframe)
    expected = set(expected_timeframes)
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise ValueError(
            f"timeframe set mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def run_multitimeframe_research(
    candles_by_timeframe: Mapping[str, list[dict]],
    *,
    expected_timeframes: tuple[str, ...] = SUPPORTED_TIMEFRAMES,
    history_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    execution_model: ExecutionModel | None = None,
    entry_timing: str = "signal_reference",
    require_contiguous: bool = False,
) -> MultiTimeframeResearchResult:
    """Validate and run the existing walk-forward engine for each timeframe.

    Every timeframe is validated independently before any result is returned.
    Weekend/session gaps remain acceptable by default; callers can request strict
    contiguous research feeds with ``require_contiguous=True``.
    """
    if not expected_timeframes:
        raise ValueError("expected_timeframes must not be empty")
    _validate_mapping_keys(candles_by_timeframe, expected_timeframes)

    results: dict[str, WalkForwardResult] = {}
    inputs: list[TimeframeResearchInput] = []

    for timeframe in expected_timeframes:
        candles = candles_by_timeframe[timeframe]
        if not isinstance(candles, list):
            raise ValueError(f"candles for {timeframe} must be a list")

        feed_bars = [_FeedBar(candle, timeframe) for candle in candles]
        integrity = validate_feed_batch(
            feed_bars,
            timeframe,
            require_utc=True,
            require_contiguous=require_contiguous,
        )
        if not integrity.ok:
            raise ValueError(f"feed integrity failed for {timeframe}: {integrity.reason}")

        result = walk_forward_backtest(
            candles,
            timeframe,
            history_bars=history_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            reward_risk=reward_risk,
            max_hold_bars=max_hold_bars,
            execution_model=execution_model,
            entry_timing=entry_timing,
        )
        results[timeframe] = result
        inputs.append(TimeframeResearchInput(timeframe, len(candles), integrity))

    report = build_multitimeframe_report(results, expected_timeframes=expected_timeframes)
    return MultiTimeframeResearchResult(report=report, results=results, inputs=tuple(inputs))


__all__ = [
    "MultiTimeframeResearchResult",
    "TimeframeResearchInput",
    "run_multitimeframe_research",
]
