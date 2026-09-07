"""Leakage-safe signal-quality diagnostics for historical paper research.

This module is deliberately post-replay. It joins an already-recorded signal
with its later paper outcome and groups the signal by decision-time metadata.
Future candles are used only to obtain the already-produced outcome label; the
regime classification itself uses the candle prefix ending at the signal bar.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Mapping, Sequence

from .paper_outcomes import PaperSignalOutcome
from .paper_session import PaperSessionResult
from .regime import classify_regime


DEFAULT_SCORE_BUCKETS = (0, 40, 60, 80, 101)


@dataclass(frozen=True)
class SignalQualityRow:
    dimension: str
    value: str
    signals: int
    opened: int
    closed: int
    wins: int
    losses: int
    skipped: int
    unresolved: int
    win_rate: float | None
    mean_r: float | None
    realized_r: float


@dataclass(frozen=True)
class SignalQualityReport:
    by_timeframe: tuple[SignalQualityRow, ...]
    by_regime: tuple[SignalQualityRow, ...]
    by_breakout_state: tuple[SignalQualityRow, ...]
    by_score_bucket: tuple[SignalQualityRow, ...]


def build_signal_quality_report(
    results: Sequence[PaperSessionResult],
    outcomes: Sequence[PaperSignalOutcome],
    candles_by_timeframe: Mapping[str, Sequence[dict]],
    *,
    strength: int = 2,
    score_buckets: tuple[int, ...] = DEFAULT_SCORE_BUCKETS,
) -> SignalQualityReport:
    """Aggregate historical paper outcomes by four decision-time dimensions.

    ``results`` and ``outcomes`` must come from the same chronological replay.
    The function rejects duplicate/missing outcome IDs and missing signal bars
    rather than silently producing a misleading report.
    """
    if strength < 1:
        raise ValueError("strength must be >= 1")
    _validate_buckets(score_buckets)

    result_by_event = {
        result.signal_event.event_id: result
        for result in results
        if result.signal_event.event_id is not None
        and result.signal_event.action in {"LONG", "SHORT"}
    }
    outcome_by_event: dict[str, PaperSignalOutcome] = {}
    for outcome in outcomes:
        if outcome.event_id in outcome_by_event:
            raise ValueError("duplicate paper outcome event_id")
        outcome_by_event[outcome.event_id] = outcome

    if set(result_by_event) != set(outcome_by_event):
        raise ValueError("results and outcomes must contain the same directional signal IDs")

    time_indices = {
        timeframe: _build_time_index(candles)
        for timeframe, candles in candles_by_timeframe.items()
    }

    rows: list[tuple[str, str, PaperSessionResult, PaperSignalOutcome]] = []
    for event_id, result in result_by_event.items():
        outcome = outcome_by_event[event_id]
        signal = result.evaluation.signal
        timeframe = result.evaluation.timeframe
        index = time_indices.get(timeframe, {}).get(_utc(result.evaluation.bar_time))
        if index is None:
            raise ValueError("signal bar_time is missing from candles_by_timeframe")
        regime = classify_regime(
            [dict(candle) for candle in candles_by_timeframe[timeframe]],
            index,
            strength=strength,
        )
        breakout = signal.breakout_state
        score_bucket = _score_bucket(signal.score.total if signal.score is not None else None, score_buckets)
        rows.extend(
            (
                ("timeframe", timeframe, result, outcome),
                ("regime", regime, result, outcome),
                ("breakout_state", breakout, result, outcome),
                ("score_bucket", score_bucket, result, outcome),
            )
        )

    return SignalQualityReport(
        by_timeframe=_aggregate("timeframe", rows),
        by_regime=_aggregate("regime", rows),
        by_breakout_state=_aggregate("breakout_state", rows),
        by_score_bucket=_aggregate("score_bucket", rows),
    )


def _aggregate(
    dimension: str,
    rows: Sequence[tuple[str, str, PaperSessionResult, PaperSignalOutcome]],
) -> tuple[SignalQualityRow, ...]:
    grouped: dict[str, list[tuple[PaperSessionResult, PaperSignalOutcome]]] = {}
    for row_dimension, value, result, outcome in rows:
        if row_dimension == dimension:
            grouped.setdefault(value, []).append((result, outcome))

    output: list[SignalQualityRow] = []
    for value in sorted(grouped):
        members = grouped[value]
        member_outcomes = [outcome for _, outcome in members]
        closed = [outcome for outcome in member_outcomes if outcome.outcome in {"WIN", "LOSS"}]
        r_values = [float(outcome.r_multiple) for outcome in closed if outcome.r_multiple is not None]
        wins = sum(outcome.outcome == "WIN" for outcome in member_outcomes)
        losses = sum(outcome.outcome == "LOSS" for outcome in member_outcomes)
        opened = sum(outcome.trade_id is not None for outcome in member_outcomes)
        skipped = sum(outcome.outcome == "SKIPPED" for outcome in member_outcomes)
        unresolved = sum(outcome.outcome == "UNRESOLVED" for outcome in member_outcomes)
        output.append(
            SignalQualityRow(
                dimension=dimension,
                value=value,
                signals=len(members),
                opened=opened,
                closed=len(closed),
                wins=wins,
                losses=losses,
                skipped=skipped,
                unresolved=unresolved,
                win_rate=wins / (wins + losses) if wins + losses else None,
                mean_r=mean(r_values) if r_values else None,
                realized_r=sum(r_values),
            )
        )
    return tuple(output)


def _build_time_index(candles: Sequence[dict]) -> dict[datetime, int]:
    index: dict[datetime, int] = {}
    for position, candle in enumerate(candles):
        value = candle.get("time")
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("candle time must be timezone-aware")
        key = value.astimezone(timezone.utc)
        if key in index:
            raise ValueError("candles contain duplicate timestamps")
        index[key] = position
    return index


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("signal bar_time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_buckets(buckets: tuple[int, ...]) -> None:
    if len(buckets) < 2 or buckets[0] != 0 or any(a >= b for a, b in zip(buckets, buckets[1:])):
        raise ValueError("score_buckets must start at 0 and be strictly increasing")
    if buckets[-1] < 101:
        raise ValueError("score_buckets must cover scores through 100")


def _score_bucket(score: int | None, buckets: tuple[int, ...]) -> str:
    if score is None:
        return "UNSCORED"
    if not 0 <= score <= 100:
        raise ValueError("setup score must be between 0 and 100")
    for lower, upper in zip(buckets, buckets[1:]):
        if lower <= score < upper:
            return f"{lower}-{upper - 1}"
    raise ValueError("score does not fit configured buckets")


__all__ = ["DEFAULT_SCORE_BUCKETS", "SignalQualityRow", "SignalQualityReport", "build_signal_quality_report"]
