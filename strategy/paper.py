"""Deterministic paper-trading engine for research and validation.

This module simulates the lifecycle of an already-approved LONG/SHORT signal.
It never connects to a broker, never calls MetaTrader5 order APIs, and never
places real orders.

The engine is bar-driven: a signal observed on one closed candle can only be
opened on a strictly later candle. Stop/target checks then consume subsequent
bars, with conservative STOP-first handling when both levels are touched in
one OHLC bar.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from .engine import EngineSignal, LONG, SHORT, WAIT
from .execution import ExecutionModel, entry_price as apply_entry_price, exit_price
from .risk import LOSS, OPEN, WIN, RiskPlan, build_risk_plan


CLOSED = "CLOSED"
SAFE = "SAFE"
NO_BREAKOUT = "NO_BREAKOUT"
STATE_VERSION = 1


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
    """Single-position, deterministic paper account for research only.

    Only LONG/SHORT signals with SAFE protection and NO_BREAKOUT state are
    accepted. WAIT is always ignored. Execution costs are applied before risk
    levels are built so stop/target geometry is consistent with the simulated
    fill price.
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

    def to_state(self) -> dict[str, Any]:
        """Return a JSON-compatible checkpoint of mutable engine state."""
        account = self.account
        return {
            "version": STATE_VERSION,
            "config": {
                "initial_balance": self._initial_balance,
                "stop_buffer": self._stop_buffer,
                "reward_risk": self._reward_risk,
                "execution_model": {
                    "spread": self._execution_model.spread,
                    "slippage": self._execution_model.slippage,
                    "commission": self._execution_model.commission,
                    "latency_bars": self._execution_model.latency_bars,
                    "price_digits": self._execution_model.price_digits,
                    "session_start": self._execution_model.session_start.isoformat() if self._execution_model.session_start else None,
                    "session_end": self._execution_model.session_end.isoformat() if self._execution_model.session_end else None,
                },
            },
            "account": {
                "initial_balance": account.initial_balance,
                "balance": account.balance,
                "realized_r": account.realized_r,
                "closed_trades": account.closed_trades,
                "wins": account.wins,
                "losses": account.losses,
            },
            "next_trade_id": self._next_trade_id,
            "position": self._position_state(self._position),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore a validated checkpoint without changing strategy semantics."""
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
            raise ValueError("unsupported or invalid paper engine state version")
        account = state.get("account")
        if not isinstance(account, dict):
            raise ValueError("paper engine state account is invalid")
        expected = self.account
        restored = PaperAccount(
            initial_balance=self._finite_positive(account.get("initial_balance"), "initial_balance"),
            balance=self._finite(account.get("balance"), "balance"),
            realized_r=self._finite(account.get("realized_r"), "realized_r"),
            closed_trades=self._non_negative_int(account.get("closed_trades"), "closed_trades"),
            wins=self._non_negative_int(account.get("wins"), "wins"),
            losses=self._non_negative_int(account.get("losses"), "losses"),
        )
        if restored.initial_balance != expected.initial_balance:
            raise ValueError("checkpoint initial_balance does not match runtime configuration")
        if restored.closed_trades != restored.wins + restored.losses:
            raise ValueError("checkpoint trade counters are inconsistent")
        if restored.balance != restored.initial_balance + restored.realized_r:
            raise ValueError("checkpoint balance is inconsistent with realized_r")

        next_trade_id = self._positive_int(state.get("next_trade_id"), "next_trade_id")
        position = self._position_from_state(state.get("position"))
        if position is not None and position.trade_id >= next_trade_id:
            raise ValueError("next_trade_id must be greater than open position trade_id")
        if position is not None and restored.closed_trades > 0 and position.trade_id < restored.closed_trades:
            raise ValueError("checkpoint trade ids are inconsistent")

        self._balance = restored.balance
        self._realized_r = restored.realized_r
        self._closed_trades = restored.closed_trades
        self._wins = restored.wins
        self._losses = restored.losses
        self._next_trade_id = next_trade_id
        self._position = position

    @staticmethod
    def _position_state(position: PaperPosition | None) -> dict[str, Any] | None:
        if position is None:
            return None
        return {
            "trade_id": position.trade_id,
            "direction": position.direction,
            "signal_time": position.signal_time.isoformat(),
            "entry_time": position.entry_time.isoformat(),
            "entry_price": position.entry_price,
            "stop": position.stop,
            "target": position.target,
            "risk_distance": position.risk_distance,
            "status": position.status,
            "exit_time": position.exit_time.isoformat() if position.exit_time else None,
            "exit_price": position.exit_price,
            "outcome": position.outcome,
            "r_multiple": position.r_multiple,
            "bars_held": position.bars_held,
        }

    @classmethod
    def _position_from_state(cls, raw: Any) -> PaperPosition | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("checkpoint position is invalid")
        direction = raw.get("direction")
        if direction not in {LONG, SHORT}:
            raise ValueError("checkpoint position direction is invalid")
        if raw.get("status") != OPEN:
            raise ValueError("only an open position may be restored")
        signal_time = cls._timestamp(raw.get("signal_time"), "signal_time")
        entry_time = cls._timestamp(raw.get("entry_time"), "entry_time")
        if entry_time <= signal_time:
            raise ValueError("checkpoint entry_time must be later than signal_time")
        risk_distance = cls._finite_positive(raw.get("risk_distance"), "risk_distance")
        return PaperPosition(
            trade_id=cls._positive_int(raw.get("trade_id"), "trade_id"),
            direction=direction,
            signal_time=signal_time,
            entry_time=entry_time,
            entry_price=cls._finite_positive(raw.get("entry_price"), "entry_price"),
            stop=cls._finite_positive(raw.get("stop"), "stop"),
            target=cls._finite_positive(raw.get("target"), "target"),
            risk_distance=risk_distance,
            status=OPEN,
            outcome=OPEN,
            r_multiple=cls._finite(raw.get("r_multiple"), "r_multiple"),
            bars_held=cls._non_negative_int(raw.get("bars_held"), "bars_held"),
        )

    @staticmethod
    def _timestamp(value: Any, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be an ISO timestamp")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _finite(value: Any, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be numeric") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name} must be finite")
        return number

    @classmethod
    def _finite_positive(cls, value: Any, field_name: str) -> float:
        number = cls._finite(value, field_name)
        if number <= 0:
            raise ValueError(f"{field_name} must be > 0")
        return number

    @classmethod
    def _positive_int(cls, value: Any, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{field_name} must be an integer >= 1")
        return value

    @classmethod
    def _non_negative_int(cls, value: Any, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name} must be an integer >= 0")
        return value

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
        signal. The fill is adjusted for configured spread/slippage before
        stop/target levels are calculated.
        """
        if signal.action == WAIT:
            return None
        if signal.action not in {LONG, SHORT}:
            raise ValueError("signal action must be LONG, SHORT, or WAIT")
        if signal.protection != SAFE:
            return None
        if signal.breakout_state not in {NO_BREAKOUT, ""}:
            return None
        if signal.zone is None:
            raise ValueError("approved signal must include a zone")
        self._validate_timestamp(signal_time, "signal_time")
        self._validate_timestamp(entry_time, "entry_time")
        if entry_time <= signal_time:
            raise ValueError("entry_time must be later than signal_time")
        if not isfinite(entry_price) or entry_price <= 0:
            raise ValueError("entry_price must be finite and > 0")
        if self._position is not None:
            return None

        effective_entry = apply_entry_price(entry_price, signal.action, self._execution_model)
        plan: RiskPlan = build_risk_plan(
            signal.action,
            effective_entry,
            signal.zone,
            self._stop_buffer,
            self._reward_risk,
        )
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
        ``None`` and leaves the position open. If both levels are touched in
        one bar, STOP wins because OHLC data cannot reveal intrabar ordering.
        """
        position = self._position
        if position is None:
            return None

        timestamp = bar.get("time")
        self._validate_timestamp(timestamp, "bar time")
        if timestamp <= position.entry_time:
            raise ValueError("bar time must be later than entry_time")

        try:
            high = float(bar["high"])
            low = float(bar["low"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("bar high/low must be numeric") from exc
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
            self._position = replace(position, bars_held=bars_held)
            return None

        outcome = LOSS if hit_stop else WIN
        raw_exit = position.stop if hit_stop else position.target
        realized_exit = exit_price(raw_exit, position.direction, self._execution_model)
        gross_r = (
            (realized_exit - position.entry_price) / position.risk_distance
            if position.direction == LONG
            else (position.entry_price - realized_exit) / position.risk_distance
        )
        realized_r = gross_r - (self._execution_model.commission / position.risk_distance)
        closed = replace(
            position,
            status=CLOSED,
            exit_time=timestamp,
            exit_price=realized_exit,
            outcome=outcome,
            r_multiple=realized_r,
            bars_held=bars_held,
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

    @staticmethod
    def _validate_timestamp(value: object, field_name: str) -> None:
        if not isinstance(value, datetime):
            raise ValueError(f"{field_name} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        if value.tzinfo != timezone.utc:
            value.astimezone(timezone.utc)
