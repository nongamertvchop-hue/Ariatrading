"""Paired statistical analysis for baseline vs filtered paper opportunities."""

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

    Baseline directional opportunities define the paired population. The MTF
    result at the same candle is paired with it; a filtered WAIT is SKIPPED and
    contributes zero realized R. UNRESOLVED pairs are excluded from CI/mean.
    """
    if bootstrap_samples < 0:
        raise ValueError("bootstrap_samples must be >= 0")
    if min_pairs_for_ci < 2:
        raise ValueError("min_pairs_for_ci must be >= 2")

    baseline_outcomes = label_paper_signals(baseline_results)
    mtf_outcomes = label_paper_signals(mtf_results)
    baseline_map = _outcome_map(baseline_outcomes)
    mtf_map = _outcome_map(mtf_outcomes)
    mtf_results_map = _result_map(mtf_results)
    keys = sorted(baseline_map)

    if not keys:
        return _empty(baseline_outcomes, mtf_outcomes, bootstrap_samples, random_seed)

    pairs: list[PairedRDelta] = []
    for key in keys:
        result = mtf_results_map.get(key)
        if result is None:
            raise ValueError("MTF replay is missing a result for a baseline opportunity")
        if result.signal_event.action in {"LONG", "SHORT"}:
            mtf = mtf_map.get(key)
            if mtf is None:
                raise ValueError("MTF directional result has no matching outcome")
        else:
            mtf = _skipped_outcome(result, key, baseline_map[key].action)
        pairs.append(_pair(key, baseline_map[key], mtf))

    resolved = [p for p in pairs if p.baseline_outcome != UNRESOLVED and p.mtf_outcome != UNRESOLVED]
    deltas = [p.delta_r for p in resolved]
    ci_available = len(deltas) >= min_pairs_for_ci and bootstrap_samples > 0
    ci_low = ci_high = None
    if ci_available:
        ci_low, ci_high = _bootstrap_mean_ci(deltas, bootstrap_samples, random_seed)

    baseline_r = _realized_r(baseline_outcomes)
    mtf_r = _realized_r(mtf_outcomes)
    baseline_closed = _closed_count(baseline_outcomes)
    mtf_closed = _closed_count(mtf_outcomes)
    return PairedStatisticalAnalysis(
        len(pairs), len(resolved), len(baseline_outcomes), len(mtf_outcomes),
        len(mtf_outcomes) - len(baseline_outcomes), baseline_closed, mtf_closed,
        mtf_closed - baseline_closed, baseline_r, mtf_r, mtf_r - baseline_r,
        mean(deltas) if deltas else None, ci_low, ci_high, bootstrap_samples,
        random_seed, ci_available,
    )


def _result_map(results: Sequence[PaperSessionResult]) -> dict[tuple[str, str, datetime], PaperSessionResult]:
    mapping: dict[tuple[str, str, datetime], PaperSessionResult] = {}
    for result in results:
        key = (result.evaluation.symbol, result.evaluation.timeframe, _utc(result.evaluation.bar_time))
        if key in mapping:
            raise ValueError("duplicate paper opportunity key")
        mapping[key] = result
    return mapping


def _outcome_map(outcomes: Sequence[PaperSignalOutcome]) -> dict[tuple[str, str, datetime], PaperSignalOutcome]:
    mapping: dict[tuple[str, str, datetime], PaperSignalOutcome] = {}
    for outcome in outcomes:
        key = (outcome.symbol, outcome.timeframe, _utc(outcome.signal_time))
        if key in mapping:
            raise ValueError("duplicate directional opportunity key")
        mapping[key] = outcome
    return mapping


def _skipped_outcome(result: PaperSessionResult, key: tuple[str, str, datetime], action: str) -> PaperSignalOutcome:
    return PaperSignalOutcome(result.signal_event.event_id, key[0], key[1], key[2], action, SKIPPED)


def _pair(key: tuple[str, str, datetime], baseline: PaperSignalOutcome, mtf: PaperSignalOutcome) -> PairedRDelta:
    if baseline.action != mtf.action:
        raise ValueError(f"paired opportunity direction mismatch at {key}")
    baseline_r = _outcome_r(baseline)
    mtf_r = _outcome_r(mtf)
    return PairedRDelta(key, baseline_r, mtf_r, mtf_r - baseline_r, baseline.outcome, mtf.outcome)


def _outcome_r(outcome: PaperSignalOutcome) -> float:
    if outcome.outcome in {SKIPPED, UNRESOLVED}:
        return 0.0
    if outcome.outcome in {WIN, LOSS}:
        if outcome.r_multiple is None:
            raise ValueError("closed paper outcome must contain r_multiple")
        return float(outcome.r_multiple)
    raise ValueError(f"unsupported paper outcome: {outcome.outcome}")


def _bootstrap_mean_ci(values: Sequence[float], samples: int, seed: int) -> tuple[float, float]:
    rng = Random(seed)
    n = len(values)
    estimates = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(samples))
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def _percentile(values: Sequence[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _closed_count(outcomes: Sequence[PaperSignalOutcome]) -> int:
    return sum(o.outcome in {WIN, LOSS} for o in outcomes)


def _realized_r(outcomes: Sequence[PaperSignalOutcome]) -> float:
    return sum(_outcome_r(o) for o in outcomes if o.outcome in {WIN, LOSS})


def _empty(baseline, mtf, samples: int, seed: int) -> PairedStatisticalAnalysis:
    br, mr = _realized_r(baseline), _realized_r(mtf)
    bc, mc = _closed_count(baseline), _closed_count(mtf)
    return PairedStatisticalAnalysis(0, 0, len(baseline), len(mtf), len(mtf) - len(baseline), bc, mc, mc - bc, br, mr, mr - br, None, None, None, samples, seed, False)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = ["DEFAULT_BOOTSTRAP_SAMPLES", "DEFAULT_MIN_PAIRS_FOR_CI", "PairedRDelta", "PairedStatisticalAnalysis", "analyze_paired_paper_outcomes"]
