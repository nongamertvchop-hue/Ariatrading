"""Deterministic historical replay through the realtime-to-paper path.

This harness intentionally reuses ``RealtimeMonitor`` and
``PaperSessionRunner``. It does not implement a second strategy or a broker
adapter. Historical candles are presented one closed candle at a time, and a
signal observed on bar N can only be filled at the OPEN of a later bar.
"""

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any, Sequence

from .paper_session import PaperSessionResult, PaperSessionRunner
from .realtime import LiveBar, LiveEvaluation, RealtimeMonitor
from .timeframe import bar_duration, get_timeframe_config


@dataclass(frozen=True)
class PaperReplayResult:
    """Completed paper-session steps produced by deterministic replay."""

    symbol: str
    timeframe: str
    results: tuple[PaperSessionResult, ...]
    final_state: dict[str, Any]

    @property
    def count(self) -> int:
        return len(self.results)

    @property
    def opened_count(self) -> int:
        return sum(result.opened is not None for result in self.results)

    @property
    def closed_count(self) -> int:
        return sum(result.closed is not None for result in self.results)

    @property
    def realized_r(self) -> float:
        return float(self.final_state["paper"]["account"]["realized_r"])

    @property
    def balance(self) -> float:
        return float(self.final_state["paper"]["account"]["balance"])


def replay_paper_session(
    candles: Sequence[dict],
    symbol: str,
    timeframe: str,
    *,
    lookback: int = 100,
    max_staleness_bars: int = 2,
    min_forecast_confidence: float = 0.45,
    start_index: int | None = None,
) -> PaperReplayResult:
    """Replay closed historical candles through the automatic paper path.

    Only candles at or before the current replay index are visible to the
    realtime monitor. The deterministic ``now`` value is derived from the
    current candle's close boundary, avoiding future-time leakage while
    satisfying the realtime freshness guard.
    """
    get_timeframe_config(timeframe)
    if not symbol:
        raise ValueError("symbol must be non-empty")
    if lookback < 10:
        raise ValueError("lookback must be at least 10")
    if not candles:
        empty = PaperSessionRunner(_EmptyMonitor())
        return PaperReplayResult(symbol, timeframe, (), empty.to_state())

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
    session = PaperSessionRunner(_DeterministicMonitor(monitor))

    results: list[PaperSessionResult] = []
    for index in range(first, len(normalized)):
        window = normalized[max(0, index - lookback + 1): index + 1]
        if len(window) < 5:
            continue
        feed.bars = [_to_live_bar(candle) for candle in window]
        now = window[-1]["time"] + bar_duration(timeframe) + timedelta(seconds=1)
        result = session.process_once(now=now)
        if result is None:
            raise RuntimeError("paper replay unexpectedly skipped a chronological candle")
        results.append(result)

    return PaperReplayResult(
        symbol=symbol,
        timeframe=timeframe,
        results=tuple(results),
        final_state=session.to_state(),
    )


class _ReplayFeed:
    def __init__(self) -> None:
        self.bars: list[LiveBar] = []

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> Sequence[LiveBar]:
        return self.bars[-count:]


class _DeterministicMonitor:
    """Make realtime evaluation timestamps deterministic for replay artifacts."""

    def __init__(self, monitor: RealtimeMonitor) -> None:
        self._monitor = monitor

    def evaluate_once(self, now=None) -> LiveEvaluation | None:
        evaluation = self._monitor.evaluate_once(now=now)
        if evaluation is None:
            return None
        return replace(
            evaluation,
            evaluated_at=evaluation.bar_time + timedelta(seconds=1),
        )


class _EmptyMonitor:
    def evaluate_once(self, now=None) -> LiveEvaluation | None:
        raise RuntimeError("empty paper replay has no monitor evaluations")


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
        raise ValueError("historical paper replay candle cannot be converted to LiveBar") from exc


__all__ = ["PaperReplayResult", "replay_paper_session"]
