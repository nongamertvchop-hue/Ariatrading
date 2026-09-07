"""Stateful portfolio risk controls surrounding, but not changing, strategy logic.

This layer is deliberately downstream of the two core LONG/SHORT setups. It
tracks session loss and equity drawdown and provides hard gates before a new
position may be opened. It does not generate signals and does not manage
broker orders.
"""

from dataclasses import dataclass
from math import isfinite


HALT = "HALT"
ALLOW = "ALLOW"


@dataclass(frozen=True)
class PortfolioRiskLimits:
    max_daily_loss_fraction: float = 0.03
    max_drawdown_fraction: float = 0.10
    max_consecutive_losses: int = 3

    def __post_init__(self) -> None:
        for name, value in {
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_drawdown_fraction": self.max_drawdown_fraction,
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


@dataclass(frozen=True)
class PortfolioRiskDecision:
    action: str
    allowed: bool
    reason: str
    daily_loss_fraction: float
    drawdown_fraction: float
    consecutive_losses: int


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
        self._state = PortfolioRiskState(
            session_start_equity=initial_equity,
            peak_equity=initial_equity,
            equity=initial_equity,
        )

    @property
    def state(self) -> PortfolioRiskState:
        return self._state

    def update_equity(self, equity: float) -> PortfolioRiskState:
        """Update equity and latch the kill switch when a hard limit is crossed."""
        if not isfinite(equity) or equity <= 0:
            raise ValueError("equity must be finite and > 0")
        state = self._state
        peak = max(state.peak_equity, equity)
        daily_loss = max(0.0, state.session_start_equity - equity)
        drawdown = max(0.0, peak - equity)
        daily_breached = daily_loss >= state.session_start_equity * self._limits.max_daily_loss_fraction
        drawdown_breached = drawdown >= peak * self._limits.max_drawdown_fraction
        halted = state.halted or daily_breached or drawdown_breached
        self._state = PortfolioRiskState(
            state.session_start_equity,
            peak,
            equity,
            daily_loss,
            state.consecutive_losses,
            halted,
        )
        return self._state

    def record_closed_trade(self, realized_pnl: float) -> PortfolioRiskState:
        """Record a closed trade and latch after too many consecutive losses."""
        if not isfinite(realized_pnl):
            raise ValueError("realized_pnl must be finite")
        state = self._state
        if realized_pnl < 0:
            consecutive = state.consecutive_losses + 1
        elif realized_pnl > 0:
            consecutive = 0
        else:
            consecutive = state.consecutive_losses
        halted = state.halted or consecutive >= self._limits.max_consecutive_losses
        self._state = PortfolioRiskState(
            state.session_start_equity,
            state.peak_equity,
            state.equity,
            state.daily_realized_loss + max(0.0, -realized_pnl),
            consecutive,
            halted,
        )
        return self._state

    def evaluate(self) -> PortfolioRiskDecision:
        """Return a hard allow/deny decision for opening the next position."""
        state = self._state
        daily_fraction = max(0.0, state.session_start_equity - state.equity) / state.session_start_equity
        drawdown_fraction = max(0.0, state.peak_equity - state.equity) / state.peak_equity
        if state.halted:
            return PortfolioRiskDecision(
                HALT,
                False,
                "portfolio risk kill switch is active",
                daily_fraction,
                drawdown_fraction,
                state.consecutive_losses,
            )
        return PortfolioRiskDecision(
            ALLOW,
            True,
            "portfolio risk limits passed",
            daily_fraction,
            drawdown_fraction,
            state.consecutive_losses,
        )

    def reset_session(self, equity: float) -> PortfolioRiskState:
        """Start a new risk session; this is the only way to clear a halt."""
        if not isfinite(equity) or equity <= 0:
            raise ValueError("equity must be finite and > 0")
        self._state = PortfolioRiskState(equity, equity, equity)
        return self._state
