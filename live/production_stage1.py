"""Fail-closed policy for the first real-money execution stage.

Stage 1 is intentionally narrow: one explicitly allow-listed symbol, a hard
risk-per-trade ceiling, a hard daily drawdown ceiling, and an exact MT5
account/server identity. This module contains deployment policy only; strategy
logic remains elsewhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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

STAGE_1 = 1
STAGE_1_MAX_SYMBOLS = 1
STAGE_1_HARD_MAX_RISK = 0.0025
STAGE_1_HARD_MAX_DAILY_DD = 0.01
STAGE_1_HARD_MAX_SPREAD_POINTS = 20.0
STAGE_1_HARD_MAX_TICK_AGE_SECONDS = 5.0


@dataclass(frozen=True)
class ProductionStage1Policy:
    """Operator-supplied Stage 1 deployment constraints."""

    stage: int
    account_login: int
    server: str
    allowed_symbols: tuple[str, ...]
    max_risk_per_trade: float
    max_daily_drawdown: float
    max_spread_points: float
    max_tick_age_seconds: float

    @classmethod
    def from_env(cls) -> "ProductionStage1Policy":
        def positive_float(name: str, default: float, hard_max: float) -> float:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise RuntimeError(f"{name} must be a finite number") from exc
            if value <= 0 or value > hard_max:
                raise RuntimeError(f"{name} must be > 0 and <= {hard_max}")
            return value

        stage_raw = os.getenv(STAGE_ENV, "0").strip()
        try:
            stage = int(stage_raw)
        except ValueError as exc:
            raise RuntimeError(f"{STAGE_ENV} must be an integer") from exc
        if stage != STAGE_1:
            raise RuntimeError(
                f"LIVE production stage is not armed: set {STAGE_ENV}={STAGE_1}"
            )

        if os.getenv(LIVE_OPT_IN_ENV, "") != LIVE_OPT_IN_VALUE:
            raise RuntimeError(
                "LIVE execution is disabled by default; explicit operator opt-in is required"
            )

        login_raw = os.getenv(ACCOUNT_ENV, "").strip()
        try:
            account_login = int(login_raw)
        except ValueError as exc:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer") from exc
        if account_login <= 0:
            raise RuntimeError(f"{ACCOUNT_ENV} must be a positive integer")

        server = os.getenv(SERVER_ENV, "").strip()
        if not server:
            raise RuntimeError(f"{SERVER_ENV} must be configured for LIVE Stage 1")

        symbols = tuple(
            symbol.strip().upper()
            for symbol in os.getenv(SYMBOLS_ENV, "").split(",")
            if symbol.strip()
        )
        if len(symbols) != STAGE_1_MAX_SYMBOLS or len(set(symbols)) != len(symbols):
            raise RuntimeError(
                f"LIVE Stage 1 requires exactly {STAGE_1_MAX_SYMBOLS} unique allow-listed symbol"
            )

        return cls(
            stage=stage,
            account_login=account_login,
            server=server,
            allowed_symbols=symbols,
            max_risk_per_trade=positive_float(MAX_RISK_ENV, STAGE_1_HARD_MAX_RISK, STAGE_1_HARD_MAX_RISK),
            max_daily_drawdown=positive_float(MAX_DAILY_DD_ENV, STAGE_1_HARD_MAX_DAILY_DD, STAGE_1_HARD_MAX_DAILY_DD),
            max_spread_points=positive_float(MAX_SPREAD_ENV, STAGE_1_HARD_MAX_SPREAD_POINTS, STAGE_1_HARD_MAX_SPREAD_POINTS),
            max_tick_age_seconds=positive_float(MAX_TICK_AGE_ENV, STAGE_1_HARD_MAX_TICK_AGE_SECONDS, STAGE_1_HARD_MAX_TICK_AGE_SECONDS),
        )

    def validate_account_identity(self, account_info: Any) -> None:
        """Reject any real account other than the exact operator allowlist."""
        actual_login = int(getattr(account_info, "login", 0))
        actual_server = str(getattr(account_info, "server", "")).strip()
        if actual_login != self.account_login or actual_server != self.server:
            raise RuntimeError(
                "LIVE Stage 1 account identity mismatch: "
                f"expected login={self.account_login}, server={self.server!r}; "
                f"got login={actual_login}, server={actual_server!r}"
            )

    def validate_symbols(self, symbols: Sequence[str]) -> None:
        normalized = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if len(normalized) != len(self.allowed_symbols) or set(normalized) != set(self.allowed_symbols):
            raise RuntimeError(
                "LIVE Stage 1 symbol allowlist mismatch: "
                f"expected {self.allowed_symbols}, got {normalized}"
            )

    def validate_runtime_limits(
        self,
        *,
        risk_per_trade: float,
        max_daily_drawdown: float,
        max_spread_points: float,
        max_tick_age_seconds: float,
    ) -> None:
        if not 0 < risk_per_trade <= self.max_risk_per_trade:
            raise RuntimeError(
                "LIVE Stage 1 risk exceeds policy: "
                f"{risk_per_trade} > {self.max_risk_per_trade}"
            )
        if not 0 < max_daily_drawdown <= self.max_daily_drawdown:
            raise RuntimeError(
                "LIVE Stage 1 daily drawdown limit exceeds policy: "
                f"{max_daily_drawdown} > {self.max_daily_drawdown}"
            )
        if not 0 < max_spread_points <= self.max_spread_points:
            raise RuntimeError(
                "LIVE Stage 1 spread limit exceeds policy: "
                f"{max_spread_points} > {self.max_spread_points}"
            )
        if not 0 < max_tick_age_seconds <= self.max_tick_age_seconds:
            raise RuntimeError(
                "LIVE Stage 1 tick-age limit exceeds policy: "
                f"{max_tick_age_seconds} > {self.max_tick_age_seconds}"
            )
