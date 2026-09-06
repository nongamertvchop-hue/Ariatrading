"""Deterministic paper-trading engine for research and validation.

This module simulates the lifecycle of an already-approved LONG/SHORT signal.
It never connects to a broker, never calls MetaTrader5 order APIs, and never
places real orders.

The engine is bar-driven: a signal observed on one closed candle can only be
opened on a strictly later candle. Stop/target checks then consume subsequent
bars, with conservative STOP-first handling when both levels are touched in a
single OHLC bar.
"""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from .engine import EngineSignal, LONG, SHORT, WAIT
from .execution import ExecutionModel
from .risk import LOSS, OPEN, WIN, RiskPlan, build_risk_plan


CLOSED = "CLOSED"


@dataclass(frozen=True)
class PaperPosition:
    trade_id: int
    direction: str
    signal_time: datetime
    entry_time: datetime
    entry_price: float
    stop: float
    target: float
    risk_distance: float
    status: str = OPEN
    exit_time: datetime | None = None
    exit_price: float | None = None
    outcome: str = OPEN
    r_multiple: float = 0.0
    bars_held: int = 0


@dataclass(frozen=True)
class PaperAccount:
    initial_balance: float
    balance: float
    realized_r: float
    closed_trades: int
    wins: int
    losses: int


class PaperTradingEngine:
    """Single-position, deterministic paper account.

    Only LONG/SHORT signals with ``protection == SAFE`` and ``breakout_state``
    equal to ``NO_BREAKOUT`` are accepted. WAIT is always ignored.
    """

    def __init__(
        self,
        *,
        initial_balance: float = 1.0,
        stop_buffer: float = 0.0,
        reward_risk: float = 2.0,
        execution_model: ExecutionModel | None = None,
    ) -> None:
        if not isfinite(initial_balance) or initial_balance <= 0:
            raise ValueError("initial_balance must be finite and > 0")
        if not isfinite(stop_buffer) or stop_buffer < 0:
            raise ValueError("stop_buffer must be finite and >= 0")
        if not isfinite(reward_risk) or reward_risk <= 0:
            raise ValueError("reward_risk must be finite and > 0")
        self._initial_balance = initial_balance
        self._balance = initial_balance
        self._realized_r = 0.0
        self._closed_trades = 0
        self._wins = 0
        self._losses = 0
        self._stop_buffer = stop_buffer
        self._reward_risk = reward_risk
        self._execution_model = execution_model or ExecutionModel()
        self._position: PaperPosition | None = None
        self._next_trade_id = 1

    @property
    def position(self) -> PaperPosition | None:
        return self._position

    @property
    def account(self) -> PaperAccount:
        return PaperAccount(
            self._initial_balance,
            self._balance,
            self._realized_r,
            self._closed_trades,
            self._wins,
            self._losses,
        )

    def open_from_signal(
        self,
        signal: EngineSignal,
        *,
        signal_time: datetime,
        entry_time: datetime,
        entry_price: float,
    ) -> PaperPosition | None:
        """Open a paper position from a prior closed-bar signal.

        ``entry_time`` must be strictly later than ``signal_time`` so the
        simulator cannot accidentally fill on the candle that generated the
        signal.
        """
        if signal.action == WAIT:
            return None
        if signal.action not in {LONG, SHORT}:
            raise ValueError("signal action must be LONG, SHORT, or WAIT")
        if signal.protection != "SAFE":
            return None
        if signal.breakout_state not in {"NO_BREAKOUT", ""}:
            return None
        if signal.zone is None:
            raise ValueError("approved signal must include a zone")
        if entry_time <= signal_time:
            raise ValueError("entry_time must be later than signal_time")
        if not isfinite(entry_price) or entry_price <= 0:
            raise ValueError("entry_price must be finite and > 0")
        if self._position is not None:
            return None

        plan: RiskPlan = build_risk_plan(
            signal.action,
            entry_price,
            signal.zone,
            self._stop_buffer,
            self._reward_risk,
        )
        effective_entry = self._apply_entry_cost(entry_price, signal.action)
        position = PaperPosition(
            trade_id=self._next_trade_id,
            direction=signal.action,
            signal_time=signal_time,
            entry_time=entry_time,
            entry_price=effective_entry,
            stop=plan.stop,
            target=plan.target,
            risk_distance=plan.risk_distance,
        )
        self._position = position
        self._next_trade_id += 1
        return position

    def on_bar(self, bar: dict) -> PaperPosition | None:
        """Advance the open position using one later OHLC bar.

        Returns the closed position when SL/TP is reached; otherwise returns
        ``None`` and leaves the position open.
        """
        position = self._position
        if position is None:
            return None
        timestamp = bar.get("time")
        if timestamp is None or not isinstance(timestamp, datetime):
            raise ValueError("bar time must be a datetime")
        if timestamp <= position.entry_time:
            raise ValueError("bar time must be later than entry_time")
        high = float(bar["high"])
        low = float(bar["low"])
        if not all(isfinite(value) for value in (high, low)) or high < low:
            raise ValueError("bar high/low must be finite and high >= low")

        bars_held = position.bars_held + 1
        if position.direction == LONG:
            hit_stop = low <= position.stop
            hit_target = high >= position.target
        else:
            hit_stop = high >= position.stop
            hit_target = low <= position.target

        if not hit_stop and not hit_target:
            self._position = PaperPosition(**{**position.__dict__, "bars_held": bars_held})
            return None

        outcome = LOSS if hit_stop else WIN
        exit_price = position.stop if hit_stop else position.target
        exit_price = self._apply_exit_cost(exit_price, position.direction)
        gross_r = (
            (exit_price - position.entry_price) / position.risk_distance
            if position.direction == LONG
            else (position.entry_price - exit_price) / position.risk_distance
        )
        realized_r = gross_r - (self._execution_model.commission / position.risk_distance)
        closed = PaperPosition(
            **{
                **position.__dict__,
                "status": CLOSED,
                "exit_time": timestamp,
                "exit_price": exit_price,
                "outcome": outcome,
                "r_multiple": realized_r,
                "bars_held": bars_held,
            }
        )
        self._realized_r += realized_r
        self._balance = self._initial_balance + self._realized_r
        self._closed_trades += 1
        if outcome == WIN:
            self._wins += 1
        else:
            self._losses += 1
        self._position = None
        return closed

    def _apply_entry_cost(self, price: float, direction: str) -> float:
        model = self._execution_model
        if direction == LONG:
            value = price + model.spread / 2 + model.slippage
        else:
            value = price - model.spread / 2 - model.slippage
        return round(value, model.price_digits) if model.price_digits is not None else value

    def _apply_exit_cost(self, price: float, direction: str) -> float:
        model = self._execution_model
        if direction == LONG:
            value = price - model.spread / 2 - model.slippage
        else:
            value = price + model.spread / 2 + model.slippage
        return round(value, model.price_digits) if model.price_digits is not None else value
