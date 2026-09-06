"""Chronological research-validation metrics for Ariatrading.

This module evaluates historical ``TradeResult`` objects only. It does not
optimize parameters, predict returns, or place orders. Splits are chronological
so later trades cannot leak into an earlier training set.
"""

from dataclasses import dataclass
import random

from .risk import LOSS, OPEN, WIN, TradeResult


@dataclass(frozen=True)
class ResearchMetrics:
    trade_count: int
    closed_trades: int
    wins: int
    losses: int
    win_rate: float
    net_r: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    average_win_r: float
    average_loss_r: float


def evaluate_trades(trades: list[TradeResult] | tuple[TradeResult, ...]) -> ResearchMetrics:
    """Calculate descriptive performance metrics without assuming profitability."""
    sample = tuple(trades)
    closed = tuple(t for t in sample if t.outcome in {WIN, LOSS})
    wins = tuple(t for t in closed if t.outcome == WIN)
    losses = tuple(t for t in closed if t.outcome == LOSS)

    net_r = sum(t.r_multiple for t in sample)
    gross_profit = sum(max(t.r_multiple, 0.0) for t in closed)
    gross_loss = sum(min(t.r_multiple, 0.0) for t in closed)
    profit_factor = float("inf") if gross_loss == 0 and gross_profit > 0 else (
        gross_profit / abs(gross_loss) if gross_loss < 0 else 0.0
    )

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for trade in sample:
        equity += trade.r_multiple
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return ResearchMetrics(
        trade_count=len(sample),
        closed_trades=len(closed),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(closed) if closed else 0.0,
        net_r=net_r,
        expectancy_r=sum(t.r_multiple for t in closed) / len(closed) if closed else 0.0,
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        average_win_r=sum(t.r_multiple for t in wins) / len(wins) if wins else 0.0,
        average_loss_r=sum(t.r_multiple for t in losses) / len(losses) if losses else 0.0,
    )


@dataclass(frozen=True)
class ChronologicalSplit:
    train: tuple[TradeResult, ...]
    validation: tuple[TradeResult, ...]
    test: tuple[TradeResult, ...]


def chronological_split(
    trades: list[TradeResult] | tuple[TradeResult, ...],
    train_ratio: float = 0.60,
    validation_ratio: float = 0.20,
) -> ChronologicalSplit:
    """Split trades in time order into train, validation and out-of-sample test."""
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be < 1")

    sample = tuple(trades)
    n = len(sample)
    train_end = int(n * train_ratio)
    validation_end = train_end + int(n * validation_ratio)
    return ChronologicalSplit(
        sample[:train_end],
        sample[train_end:validation_end],
        sample[validation_end:],
    )


def bootstrap_expectancy_ci(
    trades: list[TradeResult] | tuple[TradeResult, ...],
    iterations: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Estimate a bootstrap confidence interval for mean closed-trade R.

    This is an uncertainty estimate for the supplied historical sample, not a
    guarantee about future performance.
    """
    if iterations < 100:
        raise ValueError("iterations must be >= 100")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    values = [t.r_multiple for t in trades if t.outcome in {WIN, LOSS}]
    if not values:
        return (0.0, 0.0)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iterations):
        sample = [rng.choice(values) for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()

    alpha = (1.0 - confidence) / 2.0
    low_index = max(0, int(alpha * iterations) - 1)
    high_index = min(iterations - 1, int((1.0 - alpha) * iterations))
    return means[low_index], means[high_index]
