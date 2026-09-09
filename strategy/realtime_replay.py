"""Deterministic historical replay of the realtime monitoring path.

This harness feeds already-closed historical candles through the same
``RealtimeMonitor`` used in realtime research. It exists to detect drift
between the realtime data/strategy path and historical replay without creating
a second strategy implementation.
"""

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Sequence

from .outcomes import SignalOutcome, label_signal_outcome, label_wait_outcome
from .realtime import LiveBar, LiveEvaluation, RealtimeMonitor
from .timeframe import get_timeframe_config


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

    @property
    def event_ids(self) -> tuple[str, ...]:
        """Stable identities for each replayed closed-candle decision."""
        return tuple(evaluation.event_id for evaluation in self.evaluations)


def label_replay_outcomes(
    candles: Sequence[dict],
    replay: RealtimeReplayResult,
    *,
    target_r_multiple: float = 2.0,
    max_bars: int = 20,
) -> tuple[SignalOutcome, ...]:
    """Attach causal paper-signal outcomes to a completed realtime replay.

    Each evaluation is matched to its closed candle by timestamp. Directional
    signals are labeled from candles strictly after that signal candle; WAIT
    and supervisor-blocked decisions become ``INVALID`` rather than being
    treated as trades. The returned tuple preserves replay order and therefore
    keeps ``outcome.event_id`` aligned with ``replay.event_ids``.
    """
    if target_r_multiple <= 0:
        raise ValueError("target_r_multiple must be > 0")
    if max_bars < 1:
        raise ValueError("max_bars must be >= 1")

    normalized = [dict(candle) for candle in candles]
    positions: dict[object, int] = {}
    for index, candle in enumerate(normalized):
        timestamp = candle.get("time", candle.get("datetime"))
        if timestamp is None:
            raise ValueError("replay outcome labeling requires candle timestamps")
        if timestamp in positions:
            raise ValueError("replay outcome labeling requires unique candle timestamps")
        positions[timestamp] = index

    outcomes: list[SignalOutcome] = []
    for evaluation in replay.evaluations:
        index = positions.get(evaluation.bar_time)
        if index is None:
            raise ValueError("replay evaluation timestamp is missing from candles")

        signal = evaluation.signal
        if signal.action not in {"LONG", "SHORT"}:
            outcomes.append(label_wait_outcome(event_id=evaluation.event_id))
            continue

        if signal.entry_reference is None or signal.stop_reference is None:
            outcomes.append(label_wait_outcome(event_id=evaluation.event_id, direction=signal.action))
            continue

        outcomes.append(
            label_signal_outcome(
                event_id=evaluation.event_id,
                direction=signal.action,
                entry=signal.entry_reference,
                stop=signal.stop_reference,
                future_candles=normalized[index + 1:],
                target_r_multiple=target_r_multiple,
                max_bars=max_bars,
            )
        )

    return tuple(outcomes)


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
    timestamps merely to satisfy freshness validation. The wall-clock evaluation
    timestamp is normalized to that deterministic replay boundary in the result.
    """
    get_timeframe_config(timeframe)
    if not symbol:
        raise ValueError("symbol must be non-empty")
    if lookback < 10:
        raise ValueError("lookback must be at least 10")
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
    for index in range(first, len(normalized)):
        window = normalized[max(0, index - lookback + 1): index + 1]
        if len(window) < 5:
            continue
        feed.bars = [_to_live_bar(candle) for candle in window]
        latest_time = feed.bars[-1].time
        evaluation = monitor.evaluate_once(now=latest_time + timedelta(seconds=1))
        if evaluation is None:
            raise RuntimeError("realtime replay unexpectedly skipped a chronological candle")
        evaluations.append(replace(evaluation, evaluated_at=latest_time + timedelta(seconds=1)))

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


__all__ = ["RealtimeReplayResult", "label_replay_outcomes", "replay_realtime_monitor"]
