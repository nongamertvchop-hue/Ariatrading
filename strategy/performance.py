"""Read-only performance metrics for attributed paper-trade outcomes.

Metrics consume completed paper trades only. No strategy decisions are made
here, and no future candle information is introduced into the calculation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from statistics import mean, pstdev
from typing import Any, Iterable

from .journal import PaperTradeJournal
from .trade_attribution import PaperTradeAttribution, TradeAttribution


@dataclass(frozen=True)
class PerformanceReport:
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    gross_r: float
    average_r: float
    expectancy_r: float
    profit_factor: float | None
    max_drawdown_r: float
    average_bars_held: float
    r_stddev: float
    max_win_streak: int
    max_loss_streak: int
    current_streak: int
    current_streak_type: str | None
    recovery_factor: float | None

    def as_dict(self) -> dict[str, Any]:
        """Return strict-JSON-safe report data."""
        data = asdict(self)
        unbounded = self.profit_factor == float("inf")
        data["profit_factor"] = None if unbounded else self.profit_factor
        data["profit_factor_unbounded"] = unbounded
        return data


class PaperPerformanceAnalyzer:
    """Calculate deterministic, order-preserving paper-trade statistics."""

    def __init__(self, trades: Iterable[TradeAttribution]) -> None:
        self._trades = tuple(trades)

    @classmethod
    def from_journal(cls, journal: PaperTradeJournal) -> "PaperPerformanceAnalyzer":
        """Build an analyzer directly from a paper-trading journal."""
        return cls(PaperTradeAttribution(journal).all_trades())

    def _closed_trades(self) -> list[TradeAttribution]:
        return [
            trade
            for trade in self._trades
            if trade.is_closed and trade.r_multiple is not None
        ]

    @staticmethod
    def _sequence_metrics(r_values: list[float]) -> tuple[int, int, int, str | None]:
        if not r_values:
            return 0, 0, 0, None

        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 0
        current_type: str | None = None
        streak_type: str | None = None

        for value in r_values:
            if value > 0:
                kind = "WIN"
                max_win_streak += 0
            elif value < 0:
                kind = "LOSS"
            else:
                kind = "BREAKEVEN"

            if kind == "BREAKEVEN":
                current_streak = 0
                current_type = None
                streak_type = None
                continue

            if kind == streak_type:
                current_streak += 1
            else:
                current_streak = 1
                streak_type = kind

            current_type = kind
            if kind == "WIN":
                max_win_streak = max(max_win_streak, current_streak)
            else:
                max_loss_streak = max(max_loss_streak, current_streak)

        return max_win_streak, max_loss_streak, current_streak, current_type

    def report(self) -> PerformanceReport:
        closed = self._closed_trades()
        r_values = [float(trade.r_multiple) for trade in closed]
        for value in r_values:
            if not isfinite(value):
                raise ValueError("trade r_multiple must be finite")

        total = len(r_values)
        wins = sum(value > 0 for value in r_values)
        losses = sum(value < 0 for value in r_values)
        breakeven = total - wins - losses
        gross_r = sum(r_values)
        average_r = mean(r_values) if r_values else 0.0
        win_rate = wins / total if total else 0.0

        positive_r = sum(value for value in r_values if value > 0)
        negative_r = -sum(value for value in r_values if value < 0)
        profit_factor = positive_r / negative_r if negative_r > 0 else (float("inf") if positive_r > 0 else None)

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for value in r_values:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)

        bars = [
            trade.close_event.bars_held
            for trade in closed
            if trade.close_event is not None and trade.close_event.bars_held is not None
        ]
        average_bars = mean(bars) if bars else 0.0
        r_stddev = pstdev(r_values) if len(r_values) > 1 else 0.0
        max_win_streak, max_loss_streak, current_streak, current_streak_type = self._sequence_metrics(r_values)
        recovery_factor = gross_r / max_drawdown if max_drawdown > 0 else (float("inf") if gross_r > 0 else None)

        return PerformanceReport(
            total_trades=total,
            wins=wins,
            losses=losses,
            breakeven=breakeven,
            win_rate=win_rate,
            gross_r=gross_r,
            average_r=average_r,
            expectancy_r=average_r,
            profit_factor=profit_factor,
            max_drawdown_r=max_drawdown,
            average_bars_held=average_bars,
            r_stddev=r_stddev,
            max_win_streak=max_win_streak,
            max_loss_streak=max_loss_streak,
            current_streak=current_streak,
            current_streak_type=current_streak_type,
            recovery_factor=recovery_factor,
        )

    def by_outcome(self) -> dict[str, PerformanceReport]:
        groups: dict[str, list[TradeAttribution]] = {}
        for trade in self._trades:
            if trade.is_closed:
                outcome = trade.outcome or "UNKNOWN"
                groups.setdefault(outcome, []).append(trade)
        return {outcome: PaperPerformanceAnalyzer(trades).report() for outcome, trades in sorted(groups.items())}

    def by_dimension(self, dimension: str) -> dict[str, PerformanceReport]:
        """Group closed-trade performance by an existing journal dimension.

        Supported dimensions are ``symbol``, ``timeframe``, and ``action``.
        Values are read from the CLOSE event so a completed trade has one
        authoritative lifecycle record for the grouping key.
        """
        if dimension not in {"symbol", "timeframe", "action"}:
            raise ValueError("dimension must be one of: symbol, timeframe, action")

        groups: dict[str, list[TradeAttribution]] = {}
        for trade in self._closed_trades():
            close_event = trade.close_event
            if close_event is None:
                continue
            value = getattr(close_event, dimension)
            groups.setdefault(value, []).append(trade)

        return {
            value: PaperPerformanceAnalyzer(trades).report()
            for value, trades in sorted(groups.items())
        }

    def by_symbol(self) -> dict[str, PerformanceReport]:
        """Return closed-trade performance grouped by symbol."""
        return self.by_dimension("symbol")

    def by_timeframe(self) -> dict[str, PerformanceReport]:
        """Return closed-trade performance grouped by timeframe."""
        return self.by_dimension("timeframe")

    def by_action(self) -> dict[str, PerformanceReport]:
        """Return closed-trade performance grouped by LONG/SHORT action."""
        return self.by_dimension("action")
