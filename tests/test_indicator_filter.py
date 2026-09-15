from strategy.indicator_filter import evaluate_indicator_filter
from strategy.indicators import IndicatorSnapshot


def snapshot(*, ema20, ema50, rsi14, macd, macd_signal):
    return IndicatorSnapshot(ema20, ema50, None, rsi14, 1.0, 25.0, macd, macd_signal, None)


def test_long_is_blocked_when_all_directional_indicators_oppose():
    result = evaluate_indicator_filter(snapshot(ema20=99, ema50=100, rsi14=45, macd=-1, macd_signal=0), "LONG")
    assert result.allowed is False
    assert result.state == "OPPOSED"
    assert result.confirmations == 0


def test_short_is_blocked_when_all_directional_indicators_oppose():
    result = evaluate_indicator_filter(snapshot(ema20=101, ema50=100, rsi14=55, macd=1, macd_signal=0), "SHORT")
    assert result.allowed is False
    assert result.state == "OPPOSED"
    assert result.confirmations == 0


def test_mixed_context_does_not_veto_price_action():
    result = evaluate_indicator_filter(snapshot(ema20=101, ema50=100, rsi14=45, macd=1, macd_signal=0), "LONG")
    assert result.allowed is True
    assert result.state == "SUPPORTIVE"
    assert result.confirmations == 2


def test_unwarmed_indicators_fail_open_to_price_action():
    result = evaluate_indicator_filter(snapshot(ema20=None, ema50=None, rsi14=None, macd=None, macd_signal=None), "LONG")
    assert result.allowed is True
    assert result.state == "MIXED"
    assert result.confirmations == 0
