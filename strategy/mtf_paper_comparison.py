"""Chronological paper comparison for baseline vs MTF-filtered signals.

The comparison keeps the entry timeframe, candle window, paper execution model,
and chronological replay identical between both arms. The MTF arm only filters
an already-generated directional signal; it never creates a new setup.
"""

from dataclasses import dataclass, replace
from datetime import timedelta
from statistics import median
from typing import Sequence

from .mtf import build_timestamp_aligned_mtf_context
from .paper_session import PaperSessionResult, PaperSessionRunner
from .realtime import LiveBar, LiveEvaluation, RealtimeMonitor
from .timeframe import get_timeframe_config


@dataclass(frozen=True)
class PaperComparisonMetrics:
    signal_count: int
    opened_count: int
    closed_count: int
    wins: int
    losses: int
    unresolved: int
    skipped: int
    realized_r: float
    win_rate: float | None
    mean_r: float | None
    median_r: float | None
    signal_to_trade_rate: float | None


@dataclass(frozen=True)
class MtfPaperComparison:
    symbol: str
    timeframe: str
    results_baseline: tuple[PaperSessionResult, ...]
    results_mtf: tuple[PaperSessionResult, ...]
    baseline: PaperComparisonMetrics
    mtf: PaperComparisonMetrics

    @property
    def signal_reduction(self) -> int:
        return self.baseline.signal_count - self.mtf.signal_count

    @property
    def opened_reduction(self) -> int:
        return self.baseline.opened_count - self.mtf.opened_count

    @property
    def realized_r_delta(self) -> float:
        return self.mtf.realized_r - self.baseline.realized_r


def compare_mtf_paper_sessions(
    candles_by_timeframe: dict[str, Sequence[dict]],
    symbol: str,
    entry_timeframe: str,
    *,
    lookback: int = 100,
    max_staleness_bars: int = 2,
    min_forecast_confidence: float = 0.45,
    start_index: int | None = None,
) -> MtfPaperComparison:
    """Run identical chronological paper simulations with/without the MTF filter."""
    get_timeframe_config(entry_timeframe)
    if not symbol:
        raise ValueError("symbol must be non-empty")
    if entry_timeframe not in candles_by_timeframe:
        raise ValueError("candles_by_timeframe must contain the entry timeframe")
    entry_candles = list(candles_by_timeframe[entry_timeframe])
    if not entry_candles:
        empty = PaperSessionRunner(_EmptyMonitor())
        return MtfPaperComparison(symbol, entry_timeframe, (), (), _metrics(()), _metrics(()))
    if lookback < 10:
        raise ValueError("lookback must be at least 10")
    first = 0 if start_index is None else start_index
    if not 0 <= first < len(entry_candles):
        raise ValueError("start_index must be within entry timeframe candles")

    normalized = {tf: [dict(candle) for candle in rows] for tf, rows in candles_by_timeframe.items()}
    baseline = _replay_arm(
        normalized[entry_timeframe], symbol, entry_timeframe,
        lookback=lookback, max_staleness_bars=max_staleness_bars,
        min_forecast_confidence=min_forecast_confidence, start_index=first,
    )
    mtf = _replay_arm(
        normalized[entry_timeframe], symbol, entry_timeframe,
        lookback=lookback, max_staleness_bars=max_staleness_bars,
        min_forecast_confidence=min_forecast_confidence, start_index=first,
        filter_candles=normalized,
    )
    return MtfPaperComparison(
        symbol=symbol,
        timeframe=entry_timeframe,
        results_baseline=baseline,
        results_mtf=mtf,
        baseline=_metrics(baseline),
        mtf=_metrics(mtf),
    )


def _replay_arm(
    candles: Sequence[dict], symbol: str, timeframe: str, *,
    lookback: int, max_staleness_bars: int, min_forecast_confidence: float,
    start_index: int, filter_candles: dict[str, Sequence[dict]] | None = None,
) -> tuple[PaperSessionResult, ...]:
    feed = _ReplayFeed()
    monitor = RealtimeMonitor(
        feed, symbol, timeframe, lookback=lookback,
        max_staleness_bars=max_staleness_bars,
        min_forecast_confidence=min_forecast_confidence,
    )
    wrapped: _MonitorLike = monitor
    if filter_candles is not None:
        wrapped = _MtfFilterMonitor(monitor, filter_candles)
    session = PaperSessionRunner(wrapped)
    results: list[PaperSessionResult] = []
    for index in range(start_index, len(candles)):
        window = candles[max(0, index - lookback + 1): index + 1]
        if len(window) < 5:
            continue
        feed.bars = [_to_live_bar(candle) for candle in window]
        result = session.process_once()
        if result is None:
            raise RuntimeError("paper comparison unexpectedly skipped a chronological candle")
        results.append(result)
    return tuple(results)


class _MonitorLike:
    def evaluate_once(self, now=None) -> LiveEvaluation | None:
        raise NotImplementedError


class _MtfFilterMonitor:
    def __init__(self, monitor: RealtimeMonitor, candles_by_timeframe: dict[str, Sequence[dict]]) -> None:
        self._monitor = monitor
        self._candles_by_timeframe = candles_by_timeframe

    def evaluate_once(self, now=None) -> LiveEvaluation | None:
        evaluation = self._monitor.evaluate_once(now=now)
        if evaluation is None:
            return None
        direction = evaluation.signal.action
        if direction not in {"LONG", "SHORT"}:
            return evaluation
        close_time = evaluation.bar_time + self._duration(evaluation.timeframe)
        context = build_timestamp_aligned_mtf_context(
            self._candles_by_timeframe,
            evaluation.timeframe,
            close_time,
        )
        allowed_bias = "BULLISH" if direction == "LONG" else "BEARISH"
        if context.alignment == allowed_bias:
            return evaluation
        filtered = replace(
            evaluation.signal,
            action="WAIT",
            reason=f"MTF filter: alignment={context.alignment}",
            protection="BLOCKED",
        )
        return replace(evaluation, signal=filtered)

    @staticmethod
    def _duration(timeframe: str) -> timedelta:
        from .mtf import bar_duration
        return bar_duration(timeframe)


class _ReplayFeed:
    def __init__(self) -> None:
        self.bars: list[LiveBar] = []

    def closed_bars(self, symbol: str, timeframe: str, count: int) -> Sequence[LiveBar]:
        return self.bars[-count:]


class _EmptyMonitor:
    def evaluate_once(self, now=None):
        raise RuntimeError("empty paper comparison has no monitor evaluations")


def _to_live_bar(raw: dict) -> LiveBar:
    try:
        return LiveBar(
            raw["time"], float(raw["open"]), float(raw["high"]),
            float(raw["low"]), float(raw["close"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("historical paper comparison candle cannot be converted to LiveBar") from exc


def _metrics(results: Sequence[PaperSessionResult]) -> PaperComparisonMetrics:
    directional = [r for r in results if r.signal_event.action in {"LONG", "SHORT"}]
    closed = [r.closed for r in results if r.closed is not None]
    wins = sum(p.outcome == "WIN" for p in closed)
    losses = sum(p.outcome == "LOSS" for p in closed)
    r_values = [float(p.r_multiple) for p in closed if p.r_multiple is not None]
    skipped = sum(
        r.signal_event.action in {"LONG", "SHORT"} and r.opened is None
        for r in results[:-1]
    )
    unresolved = sum(
        r.signal_event.action in {"LONG", "SHORT"} and r.opened is None
        for r in results[-1:]
    )
    trade_rate = len(closed) / len(directional) if directional else None
    win_rate = wins / (wins + losses) if wins + losses else None
    return PaperComparisonMetrics(
        signal_count=len(directional),
        opened_count=sum(r.opened is not None for r in results),
        closed_count=len(closed),
        wins=wins,
        losses=losses,
        unresolved=unresolved,
        skipped=skipped,
        realized_r=sum(r_values),
        win_rate=win_rate,
        mean_r=(sum(r_values) / len(r_values)) if r_values else None,
        median_r=median(r_values) if r_values else None,
        signal_to_trade_rate=trade_rate,
    )


__all__ = ["MtfPaperComparison", "PaperComparisonMetrics", "compare_mtf_paper_sessions"]
