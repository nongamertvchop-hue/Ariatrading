from types import SimpleNamespace

from live.execution_outcome import Outcome, classify_exception, classify_order_result


class FakeMT5:
    TRADE_RETCODE_INVALID = 10013
    TRADE_RETCODE_INVALID_VOLUME = 10014
    TRADE_RETCODE_INVALID_PRICE = 10015
    TRADE_RETCODE_INVALID_STOPS = 10016
    TRADE_RETCODE_MARKET_CLOSED = 10018
    TRADE_RETCODE_TRADE_DISABLED = 10017
    TRADE_RETCODE_NO_MONEY = 10019
    TRADE_RETCODE_REQUOTE = 10004
    TRADE_RETCODE_PRICE_CHANGED = 10020
    TRADE_RETCODE_PRICE_OFF = 10021
    TRADE_RETCODE_TOO_MANY_REQUESTS = 10024


def test_success_is_success():
    decision = classify_order_result(SimpleNamespace(success=True, retcode=10009), FakeMT5)
    assert decision.outcome is Outcome.SUCCESS


def test_known_rejection_and_transient_are_classified():
    assert classify_order_result(SimpleNamespace(success=False, retcode=FakeMT5.TRADE_RETCODE_NO_MONEY), FakeMT5).outcome is Outcome.REJECTED
    assert classify_order_result(SimpleNamespace(success=False, retcode=FakeMT5.TRADE_RETCODE_REQUOTE), FakeMT5).outcome is Outcome.RETRYABLE


def test_unknown_or_exception_is_ambiguous():
    assert classify_order_result(SimpleNamespace(success=False, retcode=424242), FakeMT5).outcome is Outcome.AMBIGUOUS
    assert classify_exception(RuntimeError("timeout")).outcome is Outcome.AMBIGUOUS
