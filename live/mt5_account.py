"""MT5 account-mode reconciliation for the execution boundary.

The strategy must never infer whether the connected terminal is demo or real.
The terminal is the source of truth, and a mismatch is a hard execution stop.

LIVE execution is additionally disabled by default. It requires an explicit
operator opt-in in the process environment so a copied command, stale config,
or accidental mode change cannot silently reach a real account.
"""

from __future__ import annotations

import os
from typing import Any


_LIVE_OPT_IN_ENV = "ARIATRADING_ENABLE_LIVE"
_LIVE_OPT_IN_VALUE = "I_UNDERSTAND_REAL_ORDERS"


def validate_account_mode(mt5_module: Any, execution_mode: str) -> tuple[bool, str]:
    """Verify the connected MT5 account type matches the requested execution mode.

    MetaTrader 5 exposes the account trade mode through account_info().trade_mode.
    The MQL5 enum values are DEMO=0, CONTEST=1, REAL=2. We read package constants
    when available and use those documented enum values as compatibility fallbacks.

    A real-account execution request also requires an explicit process-level
    opt-in. This is intentionally independent of the broker account check.
    """
    mode = str(execution_mode).strip().upper()
    if mode not in {"DEMO", "LIVE"}:
        return True, "account mode is not applicable"

    if mode == "LIVE" and os.environ.get(_LIVE_OPT_IN_ENV) != _LIVE_OPT_IN_VALUE:
        return False, "LIVE execution is disabled by default; explicit operator opt-in is required"

    info = mt5_module.account_info()
    if info is None:
        last_error = mt5_module.last_error() if hasattr(mt5_module, "last_error") else "unknown"
        return False, f"MT5 account_info unavailable: {last_error}"

    actual = int(getattr(info, "trade_mode", -1))
    expected = 2 if mode == "LIVE" else 0
    expected_name = "ACCOUNT_TRADE_MODE_REAL" if mode == "LIVE" else "ACCOUNT_TRADE_MODE_DEMO"
    expected = int(getattr(mt5_module, expected_name, expected))

    if actual != expected:
        actual_name = {0: "DEMO", 1: "CONTEST", 2: "REAL"}.get(actual, f"UNKNOWN({actual})")
        return False, f"account mode mismatch: requested {mode}, connected account is {actual_name}"

    if not bool(getattr(info, "trade_allowed", False)):
        return False, "MT5 account does not allow trading"
    if not bool(getattr(info, "trade_expert", False)):
        return False, "MT5 Expert Advisor trading is disabled for this account"

    return True, f"account mode verified: {mode}"
