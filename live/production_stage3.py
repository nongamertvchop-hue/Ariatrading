"""Fail-closed production gate for the third LIVE execution stage.

Stage 3 is a reliability promotion, not a larger risk budget.  It keeps the
Stage 2 risk envelope while adding operational controls required before a
live executor may be considered production-ready: a kill switch, heartbeat,
position/order-count limits, reconciliation, and a startup self-test.

This module deliberately does not create broker connections or send orders.
The repository's supported runtime remains PAPER/DEMO until an execution
host is separately reviewed and explicitly enabled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from typing import Final


LIVE_OPT_IN_ENV: Final = "ARIATRADING_ENABLE_LIVE"
LIVE_OPT_IN_VALUE: Final = "I_UNDERSTAND_REAL_ORDERS"
STAGE_ENV: Final = "ARIATRADING_LIVE_STAGE"
ACCOUNT_ENV: Final = "ARIATRADING_LIVE_ACCOUNT"
SERVER_ENV: Final = "ARIATRADING_LIVE_SERVER"
SYMBOLS_ENV: Final = "ARIATRADING_LIVE_SYMBOLS"
MAX_RISK_ENV: Final = "ARIATRADING_LIVE_MAX_RISK"
MAX_DAILY_DD_ENV: Final = "ARIATRADING_LIVE_MAX_DAILY_DD"
MAX_SPREAD_ENV: Final = "ARIATRADING_LIVE_MAX_SPREAD_POINTS"
MAX_TICK_AGE_ENV: Final = "ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS"
KILL_SWITCH_ENV: Final = "ARIATRADING_LIVE_KILL_SWITCH"

STAGE_3: Final = 3
STAGE_3_MAX_SYMBOLS: Final = 2
STAGE_3_HARD_MAX_RISK: Final = 0.005
STAGE_3_HARD_MAX_DAILY_DD: Final = 0.02
STAGE_3_HARD_MAX_SPREAD_POINTS: Final = 30.0
STAGE_3_HARD_MAX_TICK_AGE_SECONDS: Final = 10.0
STAGE_3_HARD_MAX_HEARTBEAT_AGE_SECONDS: Final = 15.0
STAGE_3_HARD_MAX_OPEN_POSITIONS: Final = 2
STAGE_3_HARD_MAX_ORDERS_PER_HOUR: Final = 4


@dataclass(frozen=True)
class ProductionStage3Policy:
    """Explicit, operator-supplied Stage 3 production constraints."""

    stage: int
    account_login: int
    server: str
    allowed_symbols: tuple[str, ...]
    max_risk_per_trade: float
    max_daily_drawdown: float
    max_spread_points: float
    max_tick_age_seconds: float
    max_heartbeat_age_seconds: float = STAGE_3_HARD_MAX_HEARTBEAT_AGE_SECONDS
    max_open_positions: int = STAGE_3_HARD_MAX_OPEN_POSITIONS
    max_orders_per_hour: int = STAGE_3_HARD_MAX_ORDERS_PER_HOUR

    @classmethod
    def from_env(cls) -> "ProductionStage3Policy":
        def bounded_float(name: str, default: float, hard_max: float) -> float:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise RuntimeError(f"{name} must be a number") from exc
            if not isfinite(value) or value <= 0 or value > hard_max:
                raise RuntimeError(f"{name} must be finite, > 0 and <= {hard_max}")
            return value

        try:
            stage = int(os.getenv(STAGE_ENV, "0").strip())
        except ValueError as exc:
            raise RuntimeError(f"{STAGE_ENV} must be an integer") from exc
        if stage != STAGE_3:
            raise RuntimeError(f"Stage 3 is not armed: set {STAGE_ENV}={STAGE_3}")

        if os.getenv(LIVE_OPT_IN_ENV, "") != LIVE_OPT_IN_VALUE:
            raise RuntimeError("LIVE execution requires explicit operator opt-in")

        if os.getenv(KILL_SWITCH_ENV, "ON").strip().upper() != "OFF":
            raise RuntimeError("LIVE kill switch is active; set it to OFF only after operational checks")

        try:
            account_login = int(os.getenv(ACCOUNT_ENV, "").strip())
        except ValueError as exc:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer") from exc
        if account_login <= 0:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer")

        server = os.getenv(SERVER_ENV, "").strip()
        if not server:
            raise RuntimeError(f"{SERVER_ENV} must be configured")

        symbols = tuple(
            symbol.strip().upper()
            for symbol in os.getenv(SYMBOLS_ENV, "").split(",")
            if symbol.strip()
        )
        if not 1 <= len(symbols) <= STAGE_3_MAX_SYMBOLS or len(set(symbols)) != len(symbols):
            raise RuntimeError(
                f"Stage 3 requires 1 to {STAGE_3_MAX_SYMBOLS} unique symbols"
            )

        return cls(
            stage=stage,
            account_login=account_login,
            server=server,
            allowed_symbols=symbols,
            max_risk_per_trade=bounded_float(MAX_RISK_ENV, STAGE_3_HARD_MAX_RISK, STAGE_3_HARD_MAX_RISK),
            max_daily_drawdown=bounded_float(MAX_DAILY_DD_ENV, STAGE_3_HARD_MAX_DAILY_DD, STAGE_3_HARD_MAX_DAILY_DD),
            max_spread_points=bounded_float(MAX_SPREAD_ENV, STAGE_3_HARD_MAX_SPREAD_POINTS, STAGE_3_HARD_MAX_SPREAD_POINTS),
            max_tick_age_seconds=bounded_float(MAX_TICK_AGE_ENV, STAGE_3_HARD_MAX_TICK_AGE_SECONDS, STAGE_3_HARD_MAX_TICK_AGE_SECONDS),
        )

    def validate_account_identity(self, account_info: object) -> None:
        actual_login = int(getattr(account_info, "login", 0))
        actual_server = str(getattr(account_info, "server", "")).strip()
        if actual_login != self.account_login or actual_server != self.server:
            raise RuntimeError(
                "Stage 3 account identity mismatch: "
                f"expected login={self.account_login}, server={self.server!r}; "
                f"got login={actual_login}, server={actual_server!r}"
            )

    def validate_symbols(self, symbols: tuple[str, ...]) -> None:
        normalized = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if not normalized or len(normalized) > STAGE_3_MAX_SYMBOLS:
            raise RuntimeError("Stage 3 symbol count exceeds the hard limit")
        if len(set(normalized)) != len(normalized) or set(normalized) - set(self.allowed_symbols):
            raise RuntimeError(
                f"Stage 3 symbol allowlist mismatch: expected subset of {self.allowed_symbols}, got {normalized}"
            )

    def validate_market_state(self, *, spread_points: float, tick_age_seconds: float) -> None:
        values = (spread_points, tick_age_seconds)
        if any(not isfinite(value) for value in values):
            raise RuntimeError("Stage 3 market-state values must be finite")
        if spread_points < 0 or spread_points > self.max_spread_points:
            raise RuntimeError("Stage 3 spread safety gate rejected the market state")
        if tick_age_seconds < 0 or tick_age_seconds > self.max_tick_age_seconds:
            raise RuntimeError("Stage 3 tick freshness gate rejected the market state")

    def validate_operational_state(
        self,
        *,
        heartbeat_age_seconds: float,
        open_positions: int,
        orders_last_hour: int,
        reconciled: bool,
        startup_self_test_passed: bool,
    ) -> None:
        if not isfinite(heartbeat_age_seconds) or heartbeat_age_seconds < 0:
            raise RuntimeError("Stage 3 heartbeat age must be finite and non-negative")
        if heartbeat_age_seconds > self.max_heartbeat_age_seconds:
            raise RuntimeError("Stage 3 heartbeat is stale")
        if open_positions < 0 or open_positions > self.max_open_positions:
            raise RuntimeError("Stage 3 open-position limit exceeded")
        if orders_last_hour < 0 or orders_last_hour > self.max_orders_per_hour:
            raise RuntimeError("Stage 3 hourly order-rate limit exceeded")
        if not reconciled:
            raise RuntimeError("Stage 3 requires broker/state reconciliation before execution")
        if not startup_self_test_passed:
            raise RuntimeError("Stage 3 startup self-test has not passed")

    def validate_order_risk(self, *, risk_per_trade: float, daily_drawdown: float) -> None:
        values = (risk_per_trade, daily_drawdown)
        if any(not isfinite(value) for value in values):
            raise RuntimeError("Stage 3 risk values must be finite")
        if not 0 < risk_per_trade <= self.max_risk_per_trade:
            raise RuntimeError("Stage 3 per-trade risk limit exceeded")
        if not 0 <= daily_drawdown <= self.max_daily_drawdown:
            raise RuntimeError("Stage 3 daily drawdown limit exceeded")
