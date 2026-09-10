"""Fail-closed policy for the second real-money execution stage.

Stage 2 expands only the deployment envelope. It does not alter strategy
semantics: strategy remains LONG/SHORT/WAIT and every order still passes the
same broker, risk, idempotency and recovery boundaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from typing import Any, Sequence


LIVE_OPT_IN_ENV = "ARIATRADING_ENABLE_LIVE"
LIVE_OPT_IN_VALUE = "I_UNDERSTAND_REAL_ORDERS"
STAGE_ENV = "ARIATRADING_LIVE_STAGE"
ACCOUNT_ENV = "ARIATRADING_LIVE_ACCOUNT"
SERVER_ENV = "ARIATRADING_LIVE_SERVER"
SYMBOLS_ENV = "ARIATRADING_LIVE_SYMBOLS"
MAX_RISK_ENV = "ARIATRADING_LIVE_MAX_RISK"
MAX_DAILY_DD_ENV = "ARIATRADING_LIVE_MAX_DAILY_DD"
MAX_SPREAD_ENV = "ARIATRADING_LIVE_MAX_SPREAD_POINTS"
MAX_TICK_AGE_ENV = "ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS"

STAGE_2 = 2
STAGE_2_MAX_SYMBOLS = 2
STAGE_2_HARD_MAX_RISK = 0.005
STAGE_2_HARD_MAX_DAILY_DD = 0.02
STAGE_2_HARD_MAX_SPREAD_POINTS = 30.0
STAGE_2_HARD_MAX_TICK_AGE_SECONDS = 10.0


@dataclass(frozen=True)
class ProductionStage2Policy:
    """Operator-supplied Stage 2 deployment constraints."""

    stage: int
    account_login: int
    server: str
    allowed_symbols: tuple[str, ...]
    max_risk_per_trade: float
    max_daily_drawdown: float
    max_spread_points: float
    max_tick_age_seconds: float

    @classmethod
    def from_env(cls) -> "ProductionStage2Policy":
        def bounded_float(name: str, default: float, hard_max: float) -> float:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise RuntimeError(f"{name} must be a number") from exc
            if not isfinite(value) or value <= 0 or value > hard_max:
                raise RuntimeError(f"{name} must be a finite number > 0 and <= {hard_max}")
            return value

        try:
            stage = int(os.getenv(STAGE_ENV, "0").strip())
        except ValueError as exc:
            raise RuntimeError(f"{STAGE_ENV} must be an integer") from exc
        if stage != STAGE_2:
            raise RuntimeError(f"LIVE production stage is not armed: set {STAGE_ENV}={STAGE_2}")
        if os.getenv(LIVE_OPT_IN_ENV, "") != LIVE_OPT_IN_VALUE:
            raise RuntimeError("LIVE execution is disabled by default; explicit operator opt-in is required")

        try:
            account_login = int(os.getenv(ACCOUNT_ENV, "").strip())
        except ValueError as exc:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer") from exc
        if account_login <= 0:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer")

        server = os.getenv(SERVER_ENV, "").strip()
        if not server:
            raise RuntimeError(f"{SERVER_ENV} must be configured for LIVE Stage 2")

        symbols = tuple(
            symbol.strip().upper()
            for symbol in os.getenv(SYMBOLS_ENV, "").split(",")
            if symbol.strip()
        )
        if not 1 <= len(symbols) <= STAGE_2_MAX_SYMBOLS or len(set(symbols)) != len(symbols):
            raise RuntimeError(
                f"LIVE Stage 2 requires 1 to {STAGE_2_MAX_SYMBOLS} unique allow-listed symbols"
            )

        return cls(
            stage=stage,
            account_login=account_login,
            server=server,
            allowed_symbols=symbols,
            max_risk_per_trade=bounded_float(MAX_RISK_ENV, STAGE_2_HARD_MAX_RISK, STAGE_2_HARD_MAX_RISK),
            max_daily_drawdown=bounded_float(MAX_DAILY_DD_ENV, STAGE_2_HARD_MAX_DAILY_DD, STAGE_2_HARD_MAX_DAILY_DD),
            max_spread_points=bounded_float(MAX_SPREAD_ENV, STAGE_2_HARD_MAX_SPREAD_POINTS, STAGE_2_HARD_MAX_SPREAD_POINTS),
            max_tick_age_seconds=bounded_float(MAX_TICK_AGE_ENV, STAGE_2_HARD_MAX_TICK_AGE_SECONDS, STAGE_2_HARD_MAX_TICK_AGE_SECONDS),
        )

    def validate_account_identity(self, account_info: Any) -> None:
        actual_login = int(getattr(account_info, "login", 0))
        actual_server = str(getattr(account_info, "server", "")).strip()
        if actual_login != self.account_login or actual_server != self.server:
            raise RuntimeError(
                "LIVE Stage 2 account identity mismatch: "
                f"expected login={self.account_login}, server={self.server!r}; "
                f"got login={actual_login}, server={actual_server!r}"
            )

    def validate_symbols(self, symbols: Sequence[str]) -> None:
        normalized = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if not normalized or len(normalized) > STAGE_2_MAX_SYMBOLS or set(normalized) - set(self.allowed_symbols):
            raise RuntimeError(
                "LIVE Stage 2 symbol allowlist mismatch: "
                f"expected subset of {self.allowed_symbols}, got {normalized}"
            )

    def validate_runtime_limits(
        self,
        *,
        risk_per_trade: float,
        max_daily_drawdown: float,
        max_spread_points: float,
        max_tick_age_seconds: float,
    ) -> None:
        values = (risk_per_trade, max_daily_drawdown, max_spread_points, max_tick_age_seconds)
        if any(not isfinite(value) for value in values):
            raise RuntimeError("LIVE Stage 2 runtime limits must all be finite")
        if not 0 < risk_per_trade <= self.max_risk_per_trade:
            raise RuntimeError(f"LIVE Stage 2 risk exceeds policy: {risk_per_trade} > {self.max_risk_per_trade}")
        if not 0 < max_daily_drawdown <= self.max_daily_drawdown:
            raise RuntimeError(
                f"LIVE Stage 2 daily drawdown limit exceeds policy: {max_daily_drawdown} > {self.max_daily_drawdown}"
            )
        if not 0 < max_spread_points <= self.max_spread_points:
            raise RuntimeError(
                f"LIVE Stage 2 spread limit exceeds policy: {max_spread_points} > {self.max_spread_points}"
            )
        if not 0 < max_tick_age_seconds <= self.max_tick_age_seconds:
            raise RuntimeError(
                f"LIVE Stage 2 tick-age limit exceeds policy: {max_tick_age_seconds} > {self.max_tick_age_seconds}"
            )
