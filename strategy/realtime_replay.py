"""Deterministic historical replay of the realtime monitoring path.

This harness feeds already-closed historical candles through the same
``RealtimeMonitor`` used for realtime research. It exists to detect drift
between the realtime data/strategy path and historical replay without creating
a second strategy implementation.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

from .realtime import LiveBar, LiveEvaluation, RealtimeMonitor
from .timeframe import bar_duration, get_timeframe_config


@dataclass(frozen=True)
class RealtimeReplayResult:
    """Completed deterministic evaluations produced by realtime replay."""

    symbol: str
    timeframe: str
    evaluations: tuple[LiveEvaluation, ...]

    @property
    def count(self) -> int:
        return len(self.evaluations)

    @property
    def signals(self) -> tuple[str, ...]:
        return tuple(evaluation.signal.action for evaluation in self.evaluations)


def replay_realtime_monitor(
    candles: Sequence[dict],
    symbol: str,
    timeframe: str,
    *,
    lookback: int = 100,
    max_staleness_bars: int = 2,
    min_forecast_confidence: float = 0.45,
    start_index: int | None = None,
) -> RealtimeReplayResult:
    """Replay the production realtime-monitoring path over closed historical bars.

    The monitor receives only the prefix ending at each replay index. ``now`` is
    derived from that same latest candle, so the harness does not peek at future
    timestamps merely to satisfy freshness validation.
    """
    get_timeframe_config(timeframe)
    if not symbol:
        raise ValueError("symbol must be non-empty")
    if lookback < 5:
        raise ValueError("lookback must be at least 5")
    if not candles:
        return RealtimeReplayResult(symbol, timeframe, ())

    normalized = [dict(candle) for candle in candles]
    first = 0 if start_index is None else start_index
    if not 0 <= first < len(normalized):
        raise ValueError("start_index must be within candles")

    feed = _ReplayFeed()
    monitor = RealtimeMonitor(
        feed,
        symbol,
        timeframe,
        lookback=lookback,
        max_staleness_bars=max_staleness_bars,
        min_forecast_confidence=min_forecast_confidence,
    )

    evaluations: list[LiveEvaluation] = []
    duration = bar_duration(timeframe)
    for index in range(first, len(normalized)):
        window = normalized[max(0, index - lookback + 1): index + 1]
        if len(window) < 5:
            continue
        feed.bars = [_to_live_bar(candle) for candle in window]
        latest_time = feed.bars[-1].time
        evaluation = monitor.evaluate_once(now=latest_time + timedelta(seconds=1))
        if evaluation is None:
            raise RuntimeError("realtime replay unexpectedly skipped a chronological candle")
        evaluations.append(evaluation)

    return RealtimeReplayResult(symbol, timeframe, tuple(evaluations))


class _ReplayFeed:
    def __init__(self) -> None:
        self.bars: list[LiveBar] = []

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> Sequence[LiveBar]:
        return self.bars[-count:]


def _to_live_bar(raw: dict) -> LiveBar:
    try:
        return LiveBar(
            raw["time"],
            float(raw["open"]),
            float(raw["high"]),
            float(raw["low"]),
            float(raw["close"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("historical replay candle cannot be converted to LiveBar") from exc


__all__ = ["RealtimeReplayResult", "replay_realtime_monitor"]
