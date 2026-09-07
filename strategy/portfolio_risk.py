"""Stateful portfolio risk controls surrounding, but not changing, strategy logic.

This layer is deliberately downstream of the two core LONG/SHORT setups. It
tracks realized loss, equity drawdown, and consecutive losing outcomes and
provides hard gates before a new position may be opened. It does not generate
signals and does not manage broker orders.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite


HALT = "HALT"
ALLOW = "ALLOW"


@dataclass(frozen=True)
class PortfolioRiskLimits:
    max_daily_loss_fraction: float = 0.03
    max_drawdown_fraction: float = 0.10
    max_consecutive_losses: int = 5
    max_weekly_drawdown_fraction: float = 0.05

    def __post_init__(self) -> None:
        for name, value in {
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_drawdown_fraction": self.max_drawdown_fraction,
            "max_weekly_drawdown_fraction": self.max_weekly_drawdown_fraction,
        }.items():
            if not isfinite(value) or not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be > 0 and <= 1")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")


@dataclass(frozen=True)
class PortfolioRiskState:
    session_start_equity: float
    peak_equity: float
    equity: float
    daily_realized_loss: float = 0.0
    consecutive_losses: int = 0
    halted: bool = False
    week_start_equity: float | None = None
    week_peak_equity: float | None = None
    week_key: str | None = None


@dataclass(frozen=True)
class PortfolioRiskDecision:
    action: str
    allowed: bool
    reason: str
    daily_loss_fraction: float
    drawdown_fraction: float
    consecutive_losses: int
    weekly_drawdown_fraction: float = 0.0


class PortfolioRiskController:
    """Deterministic kill-switch state for a trading session."""

    def __init__(
        self,
        initial_equity: float,
        limits: PortfolioRiskLimits | None = None,
    ) -> None:
        if not isfinite(initial_equity) or initial_equity <= 0:
            raise ValueError("initial_equity must be finite and > 0")
        self._limits = limits or PortfolioRiskLimits()
        week_key = self._week_key(datetime.now(timezone.utc))
        self._state = PortfolioRiskState(
            session_start_equity=initial_equity,
            peak_equity=initial_equity,
            equity=initial_equity,
            week_start_equity=initial_equity,
            week_peak_equity=initial_equity,
            week_key=week_key,
        )

    @staticmethod
    def _week_key(timestamp: datetime) -> str:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        normalized = timestamp.astimezone(timezone.utc)
        iso = normalized.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    @property
    def state(self) -> PortfolioRiskState:
        return self._state

    def update_equity(self, equity: float, *, timestamp: datetime | None = None) -> PortfolioRiskState:
        """Update equity and latch hard loss limits, including weekly drawdown."""
        if not isfinite(equity) or equity <= 0:
            raise ValueError("equity must be finite and > 0")
        now = timestamp or datetime.now(timezone.utc)
        current_week = self._week_key(now)
        state = self._state

        if state.week_key != current_week:
            week_start = equity
            week_peak = equity
        else:
            week_start = state.week_start_equity or state.session_start_equity
            week_peak = max(state.week_peak_equity or week_start, equity)

        peak = max(state.peak_equity, equity)
        daily_mark_to_market_loss = max(0.0, state.session_start_equity - equity)
        daily_loss = max(daily_mark_to_market_loss, state.daily_realized_loss)
        drawdown = max(0.0, peak - equity)
        weekly_drawdown = max(0.0, week_peak - equity)
        daily_breached = daily_loss >= state.session_start_equity * self._limits.max_daily_loss_fraction
        drawdown_breached = drawdown >= peak * self._limits.max_drawdown_fraction
        weekly_breached = weekly_drawdown >= week_peak * self._limits.max_weekly_drawdown_fraction
        halted = state.halted or daily_breached or drawdown_breached or weekly_breached
        self._state = PortfolioRiskState(
            state.session_start_equity,
            peak,
            equity,
            state.daily_realized_loss,
            state.consecutive_losses,
            halted,
            week_start,
            week_peak,
            current_week,
        )
        return self._state

    def record_closed_trade(self, realized_pnl: float, *, timestamp: datetime | None = None) -> PortfolioRiskState:
        """Record a closed outcome and latch after too many consecutive losses."""
        if not isfinite(realized_pnl):
            raise ValueError("realized_pnl must be finite")
        state = self._state
        now = timestamp or datetime.now(timezone.utc)
        current_week = self._week_key(now)
        if state.week_key != current_week:
            week_start = state.equity
            week_peak = state.equity
            consecutive = 0
        else:
            week_start = state.week_start_equity or state.session_start_equity
            week_peak = state.week_peak_equity or week_start
            consecutive = state.consecutive_losses

        if realized_pnl < 0:
            consecutive += 1
        elif realized_pnl > 0:
            consecutive = 0

        daily_realized_loss = state.daily_realized_loss + max(0.0, -realized_pnl)
        weekly_drawdown = max(0.0, week_peak - state.equity)
        halted = (
            state.halted
            or consecutive >= self._limits.max_consecutive_losses
            or daily_realized_loss >= state.session_start_equity * self._limits.max_daily_loss_fraction
            or weekly_drawdown >= week_peak * self._limits.max_weekly_drawdown_fraction
        )
        self._state = PortfolioRiskState(
            state.session_start_equity,
            state.peak_equity,
            state.equity,
            daily_realized_loss,
            consecutive,
            halted,
            week_start,
            week_peak,
            current_week,
        )
        return self._state

    def evaluate(self) -> PortfolioRiskDecision:
        """Return a hard allow/deny decision for opening the next position."""
        state = self._state
        daily_loss_fraction = max(
            max(0.0, state.session_start_equity - state.equity),
            state.daily_realized_loss,
        ) / state.session_start_equity
        drawdown_fraction = max(0.0, state.peak_equity - state.equity) / state.peak_equity
        week_peak = state.week_peak_equity or state.equity
        weekly_drawdown_fraction = max(0.0, week_peak - state.equity) / week_peak
        if state.halted:
            return PortfolioRiskDecision(
                HALT,
                False,
                "portfolio risk circuit breaker is active; human reset required",
                daily_loss_fraction,
                drawdown_fraction,
                state.consecutive_losses,
                weekly_drawdown_fraction,
            )
        return PortfolioRiskDecision(
            ALLOW,
            True,
            "portfolio risk limits passed",
            daily_loss_fraction,
            drawdown_fraction,
            state.consecutive_losses,
            weekly_drawdown_fraction,
        )

    def reset_session(self, equity: float, *, timestamp: datetime | None = None) -> PortfolioRiskState:
        """Start a new risk session; this is the only way to clear a halt."""
        if not isfinite(equity) or equity <= 0:
            raise ValueError("equity must be finite and > 0")
        now = timestamp or datetime.now(timezone.utc)
        week_key = self._week_key(now)
        self._state = PortfolioRiskState(
            equity,
            equity,
            equity,
            0.0,
            0,
            False,
            equity,
            equity,
            week_key,
        )
        return self._state
