"""Forex-specific dynamic lot sizing and currency exposure management.

This module computes accurate lot sizes using MT5 symbol tick specifications
(trade_tick_value, trade_tick_size, point) so that risk remains strictly within
budget regardless of pair or account currency.

It also tracks portfolio currency exposure to prevent correlation over-leverage
(e.g., holding 3 long USD positions simultaneously).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True)
class ForexSymbolContract:
    """Normalized Forex broker symbol contract parameters."""

    symbol: str
    digits: int
    point: float
    trade_tick_value: float
    trade_tick_size: float
    volume_min: float
    volume_max: float
    volume_step: float

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.digits < 0:
            raise ValueError("digits must be >= 0")
        for name, value in {
            "point": self.point,
            "trade_tick_value": self.trade_tick_value,
            "trade_tick_size": self.trade_tick_size,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
        }.items():
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max must be >= volume_min")


@dataclass(frozen=True)
class ForexRiskLimits:
    """Hard risk limits for Forex execution."""

    risk_per_trade_fraction: float = 0.01  # 1% per trade
    max_daily_loss_fraction: float = 0.03   # 3% daily drawdown stop
    max_open_positions: int = 3
    max_positions_per_currency: int = 2     # Max positions sharing a currency (e.g. USD)

    def __post_init__(self) -> None:
        if not 0.0 < self.risk_per_trade_fraction <= 1.0:
            raise ValueError("risk_per_trade_fraction must be in (0, 1]")
        if not 0.0 < self.max_daily_loss_fraction <= 1.0:
            raise ValueError("max_daily_loss_fraction must be in (0, 1]")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be >= 1")
        if self.max_positions_per_currency < 1:
            raise ValueError("max_positions_per_currency must be >= 1")


@dataclass(frozen=True)
class ForexRiskDecision:
    """Sizing and validation decision for a Forex trade setup."""

    allowed: bool
    reason: str
    lot_size: float = 0.0
    risk_amount: float = 0.0
    risk_fraction: float = 0.0
    sl_points: float = 0.0
    sl_pips: float = 0.0


def extract_currencies(symbol: str) -> tuple[str, str]:
    """Extract 3-letter base and quote currencies from standard Forex symbol."""
    clean = "".join(ch for ch in symbol.upper() if ch.isalpha())
    if len(clean) < 6:
        return clean, ""
    return clean[:3], clean[3:6]


def check_currency_exposure(
    candidate_symbol: str,
    active_symbols: Sequence[str],
    max_per_currency: int = 2,
) -> tuple[bool, str]:
    """Verify that adding candidate_symbol does not exceed currency concentration limits."""
    base, quote = extract_currencies(candidate_symbol)
    if not base or not quote:
        return True, "non-standard symbol format; currency exposure check skipped"

    counts: dict[str, int] = {}
    for sym in active_symbols:
        s_base, s_quote = extract_currencies(sym)
        if s_base:
            counts[s_base] = counts.get(s_base, 0) + 1
        if s_quote:
            counts[s_quote] = counts.get(s_quote, 0) + 1

    if counts.get(base, 0) >= max_per_currency:
        return False, f"currency concentration limit reached for {base} ({counts[base]} active >= {max_per_currency})"
    if counts.get(quote, 0) >= max_per_currency:
        return False, f"currency concentration limit reached for {quote} ({counts[quote]} active >= {max_per_currency})"

    return True, "currency exposure checks passed"


def calculate_forex_lot_size(
    *,
    equity: float,
    entry: float,
    stop: float,
    contract: ForexSymbolContract,
    risk_fraction: float,
) -> float:
    """Calculate exact lot size floored to broker volume step."""
    if equity <= 0 or not isfinite(equity):
        raise ValueError("equity must be finite and > 0")
    if entry == stop:
        raise ValueError("entry and stop must differ")
    if not 0.0 < risk_fraction <= 1.0:
        raise ValueError("risk_fraction must be in (0, 1]")

    risk_budget = equity * risk_fraction
    price_dist = round(abs(entry - stop), contract.digits)
    ticks = price_dist / contract.trade_tick_size
    risk_per_lot = ticks * contract.trade_tick_value

    if risk_per_lot <= 0:
        return 0.0

    raw_lots = risk_budget / risk_per_lot
    # Floor to volume_step with epsilon to avoid float representation artifacts
    step = contract.volume_step
    num_steps = int((raw_lots + 1e-9) / step)
    floored_lots = num_steps * step
    return round(floored_lots, 4)


def evaluate_forex_risk(
    *,
    equity: float,
    entry: float,
    stop: float,
    contract: ForexSymbolContract,
    limits: ForexRiskLimits,
    daily_realized_loss: float = 0.0,
    active_symbols: Sequence[str] = (),
) -> ForexRiskDecision:
    """Comprehensive Forex risk evaluation including lot sizing and currency limits."""
    if equity <= 0:
        return ForexRiskDecision(False, "equity must be > 0")
    if daily_realized_loss >= equity * limits.max_daily_loss_fraction:
        return ForexRiskDecision(False, f"daily loss limit reached ({daily_realized_loss:.2f} >= {equity * limits.max_daily_loss_fraction:.2f})")
    if len(active_symbols) >= limits.max_open_positions:
        return ForexRiskDecision(False, f"maximum open positions reached ({len(active_symbols)} >= {limits.max_open_positions})")

    # Currency exposure
    exp_ok, exp_reason = check_currency_exposure(contract.symbol, active_symbols, limits.max_positions_per_currency)
    if not exp_ok:
        return ForexRiskDecision(False, exp_reason)

    price_dist = abs(entry - stop)
    sl_points = price_dist / contract.point
    # For 5-digit and 3-digit broker quotes, 1 pip = 10 points
    sl_pips = sl_points / 10.0 if contract.digits in {3, 5} else sl_points

    lots = calculate_forex_lot_size(
        equity=equity,
        entry=entry,
        stop=stop,
        contract=contract,
        risk_fraction=limits.risk_per_trade_fraction,
    )

    if lots < contract.volume_min:
        return ForexRiskDecision(
            allowed=False,
            reason=f"computed lot size {lots:.4f} is below broker minimum {contract.volume_min}",
            sl_points=sl_points,
            sl_pips=sl_pips,
        )

    if lots > contract.volume_max:
        lots = contract.volume_max

    ticks = price_dist / contract.trade_tick_size
    risk_amount = round(ticks * contract.trade_tick_value * lots, 2)
    max_budget = equity * limits.risk_per_trade_fraction

    if risk_amount > max_budget * (1.0 + 1e-9):
        return ForexRiskDecision(
            allowed=False,
            reason="calculated risk exceeded risk budget",
            sl_points=sl_points,
            sl_pips=sl_pips,
        )

    return ForexRiskDecision(
        allowed=True,
        reason="forex risk checks passed",
        lot_size=lots,
        risk_amount=risk_amount,
        risk_fraction=risk_amount / equity,
        sl_points=sl_points,
        sl_pips=sl_pips,
    )
