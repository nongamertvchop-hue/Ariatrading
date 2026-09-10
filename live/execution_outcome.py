"""Conservative classification of broker execution outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    RETRYABLE = "RETRYABLE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class OutcomeDecision:
    outcome: Outcome
    reason: str


def classify_order_result(result: Any, mt5_module: Any | None = None) -> OutcomeDecision:
    """Classify known retcodes; unknown results are AMBIGUOUS, never retried blindly."""
    if result is None:
        return OutcomeDecision(Outcome.AMBIGUOUS, "broker returned no result")
    if bool(getattr(result, "success", False)):
        return OutcomeDecision(Outcome.SUCCESS, "executor reported success")

    retcode = int(getattr(result, "retcode", -1))
    module = mt5_module
    rejected = {
        int(getattr(module, name, -10_000 - index))
        for index, name in enumerate((
            "TRADE_RETCODE_INVALID",
            "TRADE_RETCODE_INVALID_VOLUME",
            "TRADE_RETCODE_INVALID_PRICE",
            "TRADE_RETCODE_INVALID_STOPS",
            "TRADE_RETCODE_MARKET_CLOSED",
            "TRADE_RETCODE_TRADE_DISABLED",
            "TRADE_RETCODE_NO_MONEY",
        ))
    } if module is not None else set()
    retryable = {
        int(getattr(module, name, -20_000 - index))
        for index, name in enumerate((
            "TRADE_RETCODE_REQUOTE",
            "TRADE_RETCODE_PRICE_CHANGED",
            "TRADE_RETCODE_PRICE_OFF",
            "TRADE_RETCODE_TOO_MANY_REQUESTS",
        ))
    } if module is not None else set()

    if retcode in rejected:
        return OutcomeDecision(Outcome.REJECTED, f"broker rejected request retcode={retcode}")
    if retcode in retryable:
        return OutcomeDecision(Outcome.RETRYABLE, f"broker reported transient retcode={retcode}")
    return OutcomeDecision(Outcome.AMBIGUOUS, f"unclassified broker outcome retcode={retcode}")


def classify_exception(exc: BaseException) -> OutcomeDecision:
    """Transport/runtime exceptions are ambiguous because the broker may have accepted the request."""
    return OutcomeDecision(Outcome.AMBIGUOUS, f"execution exception requires reconciliation: {exc}")
