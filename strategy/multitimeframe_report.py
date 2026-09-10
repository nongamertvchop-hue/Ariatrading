"""Cross-timeframe research reporting for chronological OOS results.

This module is descriptive only. It does not optimize or select a timeframe.
Each row is derived from an already-computed walk-forward result, preserving the
strategy and execution assumptions used by that result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from .walk_forward import WalkForwardResult


@dataclass(frozen=True)
class TimeframeResearchRow:
    timeframe: str
    history_bars: int
    test_bars: int
    step_bars: int
    fold_count: int
    candles_tested: int
    trade_count: int
    closed_trades: int
    wins: int
    losses: int
    win_rate: float
    net_r: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    positive_net_r_folds: int
    profitable_fold_ratio: float

    @classmethod
    def from_result(cls, result: WalkForwardResult) -> "TimeframeResearchRow":
        metrics = result.metrics
        positive_folds = sum(fold.metrics.net_r > 0 for fold in result.folds)
        return cls(
            timeframe=result.timeframe,
            history_bars=result.history_bars,
            test_bars=result.test_bars,
            step_bars=result.step_bars,
            fold_count=result.fold_count,
            candles_tested=result.total_test_bars,
            trade_count=metrics.trade_count,
            closed_trades=metrics.closed_trades,
            wins=metrics.wins,
            losses=metrics.losses,
            win_rate=metrics.win_rate,
            net_r=metrics.net_r,
            expectancy_r=metrics.expectancy_r,
            profit_factor=metrics.profit_factor,
            max_drawdown_r=metrics.max_drawdown_r,
            positive_net_r_folds=positive_folds,
            profitable_fold_ratio=positive_folds / result.fold_count if result.fold_count else 0.0,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MultiTimeframeReport:
    rows: tuple[TimeframeResearchRow, ...]
    common_history_bars: int | None
    common_test_bars: int | None
    common_step_bars: int | None

    @property
    def timeframe_count(self) -> int:
        return len(self.rows)

    @property
    def consistently_profitable_timeframes(self) -> int:
        return sum(row.profitable_fold_ratio >= 0.5 and row.net_r > 0 for row in self.rows)

    def to_dict(self) -> dict[str, object]:
        return {
            "timeframe_count": self.timeframe_count,
            "common_history_bars": self.common_history_bars,
            "common_test_bars": self.common_test_bars,
            "common_step_bars": self.common_step_bars,
            "consistently_profitable_timeframes": self.consistently_profitable_timeframes,
            "rows": [row.to_dict() for row in self.rows],
        }


def _common_value(values: list[int]) -> int | None:
    if not values or len(set(values)) != 1:
        return None
    return values[0]


def build_multitimeframe_report(
    results: Mapping[str, WalkForwardResult],
    *,
    expected_timeframes: tuple[str, ...] | None = None,
) -> MultiTimeframeReport:
    """Build a deterministic comparison table without ranking or optimization."""
    if not results:
        return MultiTimeframeReport((), None, None, None)

    rows: list[TimeframeResearchRow] = []
    for timeframe in sorted(results):
        result = results[timeframe]
        if result.timeframe != timeframe:
            raise ValueError(
                f"mapping key {timeframe!r} does not match result timeframe {result.timeframe!r}"
            )
        for value_name, value in (
            ("history_bars", result.history_bars),
            ("test_bars", result.test_bars),
            ("step_bars", result.step_bars),
        ):
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{value_name} must be a positive integer")
        rows.append(TimeframeResearchRow.from_result(result))

    if expected_timeframes is not None:
        expected = set(expected_timeframes)
        actual = {row.timeframe for row in rows}
        missing = expected - actual
        extra = actual - expected
        if missing or extra:
            raise ValueError(
                f"timeframe set mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )

    return MultiTimeframeReport(
        rows=tuple(rows),
        common_history_bars=_common_value([row.history_bars for row in rows]),
        common_test_bars=_common_value([row.test_bars for row in rows]),
        common_step_bars=_common_value([row.step_bars for row in rows]),
    )


__all__ = ["MultiTimeframeReport", "TimeframeResearchRow", "build_multitimeframe_report"]
