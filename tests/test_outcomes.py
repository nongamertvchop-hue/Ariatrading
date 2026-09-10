from datetime import datetime, timezone

import pytest

from strategy.outcomes import AMBIGUOUS, LONG, LOSS, SHORT, TIMEOUT, WIN, label_signal_outcome


def candle(high, low, time=None):
    return {"high": high, "low": low, "time": time}


def test_long_target_hit():
    result = label_signal_outcome(
        event_id="sig_win",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        future_candles=[candle(101.0, 99.5), candle(102.0, 100.5)],
    )
    assert result.outcome == WIN
    assert result.bars_to_resolution == 2


def test_short_target_hit():
    result = label_signal_outcome(
        event_id="sig_short_win",
        direction=SHORT,
        entry=100.0,
        stop=101.0,
        target_r_multiple=2.0,
        future_candles=[candle(100.5, 99.5), candle(99.0, 98.5)],
    )
    assert result.outcome == WIN


def test_long_stop_hit():
    result = label_signal_outcome(
        event_id="sig_loss",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        future_candles=[candle(100.5, 98.5)],
    )
    assert result.outcome == LOSS


def test_same_bar_stop_and_target_is_ambiguous():
    result = label_signal_outcome(
        event_id="sig_ambiguous",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        future_candles=[candle(102.0, 98.0)],
    )
    assert result.outcome == AMBIGUOUS


def test_timeout_when_no_terminal_event():
    result = label_signal_outcome(
        event_id="sig_timeout",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        max_bars=2,
        future_candles=[candle(100.5, 99.5), candle(100.75, 99.75), candle(103.0, 98.0)],
    )
    assert result.outcome == TIMEOUT
    assert result.bars_observed == 2


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError, match="direction"):
        label_signal_outcome(
            event_id="sig_invalid",
            direction="BUY",
            entry=100.0,
            stop=99.0,
            future_candles=[],
        )
    with pytest.raises(ValueError, match="stop"):
        label_signal_outcome(
            event_id="sig_invalid_stop",
            direction=LONG,
            entry=100.0,
            stop=101.0,
            future_candles=[],
        )


def test_future_candles_are_bounded_by_max_bars():
    result = label_signal_outcome(
        event_id="sig_bound",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        max_bars=1,
        future_candles=[candle(100.5, 99.5), candle(102.0, 100.0)],
    )
    assert result.outcome == TIMEOUT
    assert result.bars_observed == 1


def test_target_overflow_fails_closed():
    with pytest.raises(ValueError, match="target"):
        label_signal_outcome(
            event_id="sig_target_overflow",
            direction=LONG,
            entry=1.0e308,
            stop=1.0,
            target_r_multiple=2.0,
            future_candles=[],
        )


def test_derived_mfe_mae_overflow_fails_closed():
    # The previous fixture stayed finite. Make the risk distance tiny enough
    # that a finite price excursion actually overflows the R-multiple metric.
    with pytest.raises(ValueError, match="MFE/MAE"):
        label_signal_outcome(
            event_id="sig_metric_overflow",
            direction=LONG,
            entry=2.0e-308,
            stop=1.0e-308,
            target_r_multiple=2.0,
            future_candles=[candle(1.0e308, 1.0e-308)],
        )
