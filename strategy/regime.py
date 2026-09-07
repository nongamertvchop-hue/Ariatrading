"""Leakage-safe market-regime stratification for research diagnostics.

Regime is a reporting dimension, not an entry setup. It is derived from a
historical candle prefix only, so future candles cannot change an earlier
regime assignment. Supervised labels may be used for outcome aggregation,
but never for regime classification.
"""

from dataclasses import dataclass

from .market_structure import BEARISH, BULLISH, RANGE, UNKNOWN, analyze_market_structure
from .ml_features import MLSample

REGIMES = (BULLISH, BEARISH, RANGE, UNKNOWN)


@dataclass(frozen=True)
class RegimeStats:
    regime: str
    samples: int
    positive: int

    @property
    def positive_rate(self) -> float:
        return self.positive / self.samples if self.samples else 0.0


def classify_regime(candles: list[dict], index: int, *, strength: int = 2) -> str:
    """Classify one decision point using candles through ``index`` only."""
    if not 0 <= index < len(candles):
        raise ValueError("index must be within candles")
    if strength < 1:
        raise ValueError("strength must be >= 1")
    return analyze_market_structure(candles[: index + 1], strength=strength).bias


def stratify_samples(
    candles: list[dict],
    samples: tuple[MLSample, ...] | list[MLSample],
    *,
    strength: int = 2,
) -> tuple[RegimeStats, ...]:
    """Aggregate supervised outcomes by decision-time market regime."""
    counts = {regime: [0, 0] for regime in REGIMES}
    for sample in samples:
        if not 0 <= sample.index < len(candles):
            raise ValueError("sample index must be within candles")
        regime = classify_regime(candles, sample.index, strength=strength)
        counts[regime][0] += 1
        counts[regime][1] += int(sample.label)
    return tuple(
        RegimeStats(regime=regime, samples=counts[regime][0], positive=counts[regime][1])
        for regime in REGIMES
    )


__all__ = ["BEARISH", "BULLISH", "RANGE", "UNKNOWN", "REGIMES", "RegimeStats", "classify_regime", "stratify_samples"]
