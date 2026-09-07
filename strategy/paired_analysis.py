"""Paired statistical analysis for baseline vs filtered paper opportunities.

This module is post-replay only. It pairs the two arms by the same
symbol/timeframe/signal-candle timestamp, so filtering an opportunity cannot
silently change the comparison population. No future candle is inspected here;
only already-recorded paper outcomes are consumed.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random
from statistics import mean
from typing import Sequence

from .paper_outcomes import LOSS, SKIPPED, UNRESOLVED, WIN, PaperSignalOutcome, label_paper_signals
from .paper_session import PaperSessionResult


DEFAULT_BOOTSTRAP_SAMPLES = 5000
DEFAULT_MIN_PAIRS_FOR_CI = 20


@dataclass(frozen=True)
class PairedRDelta:
    key: tuple[str, str, datetime]
    baseline_r: float
    mtf_r: float
    delta_r: float
    baseline_outcome: str
    mtf_outcome: str


@dataclass(frozen=True)
class PairedStatisticalAnalysis:
    paired_count: int
    resolved_pair_count: int
    baseline_signal_count: int
    mtf_signal_count: int
    signal_count_delta: int
    baseline_closed_count: int
    mtf_closed_count: int
    closed_count_delta: int
    baseline_realized_r: float
    mtf_realized_r: float
    realized_r_delta: float
    mean_r_delta: float | None
    bootstrap_ci_low: float | None
    bootstrap_ci_high: float | None
    bootstrap_samples: int
    random_seed: int
    ci_available: bool


def analyze_paired_paper_outcomes(
    baseline_results: Sequence[PaperSessionResult],
    mtf_results: Sequence[PaperSessionResult],
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    random_seed: int = 0,
    min_pairs_for_ci: int = DEFAULT_MIN_PAIRS_FOR_CI,
) -> PairedStatisticalAnalysis:
    """Compare two chronological paper replays on identical opportunities.

    Directional signals are paired by ``(symbol, timeframe, signal_time)``.
    SKIPPED means no realized trade and contributes zero R. UNRESOLVED pairs are
    excluded from the statistical sample because their eventual outcome is not
    known. The bootstrap is deterministic when ``random_seed`` is fixed.
    """
    if bootstrap_samples < 0:
        raise ValueError("bootstrap_samples must be >= 0")
    if min_pairs_for_ci < 2:
        raise ValueError("min_pairs_for_ci must be >= 2")

    baseline_outcomes = label_paper_signals(baseline_results)
    mtf_outcomes = label_paper_signals(mtf_results)
    baseline_map = _outcome_map(baseline_outcomes)
    mtf_map = _outcome_map(mtf_outcomes)
    shared_keys = sorted(set(baseline_map) | set(mtf_map))

    if not shared_keys:
        return PairedStatisticalAnalysis(
            0, 0, len(baseline_outcomes), len(mtf_outcomes),
            len(mtf_outcomes) - len(baseline_outcomes),
            _closed_count(baseline_outcomes), _closed_count(mtf_outcomes),
            _closed_count(mtf_outcomes) - _closed_count(baseline_outcomes),
            _realized_r(baseline_outcomes), _realized_r(mtf_outcomes),
            None, None, None, bootstrap_samples, random_seed, False,
        )

    if set(baseline_map) != set(mtf_map):
        raise ValueError("baseline and MTF outcomes must cover the same directional opportunity keys")

    pairs = [_pair(key, baseline_map[key], mtf_map[key]) for key in shared_keys]
    resolved = [pair for pair in pairs if pair.baseline_outcome != UNRESOLVED and pair.mtf_outcome != UNRESOLVED]
    deltas = [pair.delta_r for pair in resolved]
    ci_available = len(deltas) >= min_pairs_for_ci and bootstrap_samples > 0
    ci_low = ci_high = None
    if ci_available:
        ci_low, ci_high = _bootstrap_mean_ci(deltas, bootstrap_samples, random_seed)

    return PairedStatisticalAnalysis(
        paired_count=len(pairs),
        resolved_pair_count=len(resolved),
        baseline_signal_count=len(baseline_outcomes),
        mtf_signal_count=len(mtf_outcomes),
        signal_count_delta=len(mtf_outcomes) - len(baseline_outcomes),
        baseline_closed_count=_closed_count(baseline_outcomes),
        mtf_closed_count=_closed_count(mtf_outcomes),
        closed_count_delta=_closed_count(mtf_outcomes) - _closed_count(baseline_outcomes),
        baseline_realized_r=_realized_r(baseline_outcomes),
        mtf_realized_r=_realized_r(mtf_outcomes),
        realized_r_delta=_realized_r(mtf_outcomes) - _realized_r(baseline_outcomes),
        mean_r_delta=mean(deltas) if deltas else None,
        bootstrap_ci_low=ci_low,
        bootstrap_ci_high=ci_high,
        bootstrap_samples=bootstrap_samples,
        random_seed=random_seed,
        ci_available=ci_available,
    )


def _outcome_map(outcomes: Sequence[PaperSignalOutcome]) -> dict[tuple[str, str, datetime], PaperSignalOutcome]:
    mapping: dict[tuple[str, str, datetime], PaperSignalOutcome] = {}
    for outcome in outcomes:
        key = (outcome.symbol, outcome.timeframe, _utc(outcome.signal_time))
        if key in mapping:
            raise ValueError("duplicate directional opportunity key")
        mapping[key] = outcome
    return mapping


def _pair(key: tuple[str, str, datetime], baseline: PaperSignalOutcome, mtf: PaperSignalOutcome) -> PairedRDelta:
    if baseline.action != mtf.action:
        raise ValueError(f"paired opportunity direction mismatch at {key}")
    return PairedRDelta(
        key=key,
        baseline_r=_outcome_r(baseline),
        mtf_r=_outcome_r(mtf),
        delta_r=_outcome_r(mtf) - _outcome_r(baseline),
        baseline_outcome=baseline.outcome,
        mtf_outcome=mtf.outcome,
    )


def _outcome_r(outcome: PaperSignalOutcome) -> float:
    if outcome.outcome in {SKIPPED}:
        return 0.0
    if outcome.outcome in {WIN, LOSS}:
        if outcome.r_multiple is None:
            raise ValueError("closed paper outcome must contain r_multiple")
        return float(outcome.r_multiple)
    if outcome.outcome == UNRESOLVED:
        return 0.0
    raise ValueError(f"unsupported paper outcome: {outcome.outcome}")


def _bootstrap_mean_ci(values: Sequence[float], samples: int, seed: int) -> tuple[float, float]:
    rng = Random(seed)
    n = len(values)
    estimates = [mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(samples)]
    estimates.sort()
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _closed_count(outcomes: Sequence[PaperSignalOutcome]) -> int:
    return sum(outcome.outcome in {WIN, LOSS} for outcome in outcomes)


def _realized_r(outcomes: Sequence[PaperSignalOutcome]) -> float:
    return sum(_outcome_r(outcome) for outcome in outcomes if outcome.outcome in {WIN, LOSS})


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("signal_time must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = [
    "DEFAULT_BOOTSTRAP_SAMPLES",
    "DEFAULT_MIN_PAIRS_FOR_CI",
    "PairedRDelta",
    "PairedStatisticalAnalysis",
    "analyze_paired_paper_outcomes",
]
