"""MT5 account-mode reconciliation for the execution boundary.

The strategy must never infer whether the connected terminal is demo or real.
The terminal is the source of truth, and a mismatch is a hard execution stop.

LIVE execution additionally requires the Stage 1 deployment policy: explicit
operator opt-in, exact account/server allowlisting, and a narrow execution
profile. The production policy is intentionally separate from strategy logic.
"""

from __future__ import annotations

from typing import Any

from live.production_stage1 import ProductionStage1Policy


def validate_account_mode(mt5_module: Any, execution_mode: str) -> tuple[bool, str]:
    """Verify the connected MT5 account type matches the requested execution mode."""
    mode = str(execution_mode).strip().upper()
    if mode not in {"DEMO", "LIVE"}:
        return True, "account mode is not applicable"

    if mode == "LIVE":
        try:
            policy = ProductionStage1Policy.from_env()
        except RuntimeError as exc:
            return False, str(exc)
    else:
        policy = None

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

    if policy is not None:
        try:
            policy.validate_account_identity(info)
        except RuntimeError as exc:
            return False, str(exc)

    return True, f"account mode verified: {mode}"
