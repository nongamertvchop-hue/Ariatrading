import pytest

from strategy.outcomes import AMBIGUOUS, LOSS, LONG, SHORT, TIMEOUT, WIN, label_signal_outcome


def candle(high, low, time=None):
    raw = {"high": high, "low": low}
    if time is not None:
        raw["time"] = time
    return raw


def test_long_target_is_win_and_uses_first_terminal_bar():
    result = label_signal_outcome(
        event_id="sig_test_long",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        future_candles=[candle(101.0, 99.5), candle(102.0, 100.5)],
    )

    assert result.outcome == WIN
    assert result.bars_to_resolution == 2
    assert result.resolved_at is None
    assert result.target == 102.0
    assert result.mfe_r == 2.0
    assert result.mae_r == -0.5


def test_short_stop_is_loss():
    result = label_signal_outcome(
        event_id="sig_test_short",
        direction=SHORT,
        entry=100.0,
        stop=101.0,
        target_r_multiple=2.0,
        future_candles=[candle(100.5, 99.0), candle(101.1, 99.5)],
    )

    assert result.outcome == LOSS
    assert result.bars_to_resolution == 2
    assert result.target == 98.0
    assert result.mfe_r == 1.0
    assert result.mae_r == pytest.approx(-1.1)


def test_same_bar_stop_and_target_is_ambiguous():
    result = label_signal_outcome(
        event_id="sig_test_ambiguous",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        future_candles=[candle(102.0, 99.0, "2026-09-09T10:00:00Z")],
    )

    assert result.outcome == AMBIGUOUS
    assert result.bars_to_resolution == 1
    assert result.resolved_at == "2026-09-09T10:00:00Z"


def test_no_terminal_event_by_horizon_is_timeout():
    result = label_signal_outcome(
        event_id="sig_test_timeout",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        max_bars=2,
        future_candles=[candle(100.5, 99.5), candle(101.0, 100.0), candle(102.0, 99.0)],
    )

    assert result.outcome == TIMEOUT
    assert result.bars_observed == 2
    assert result.bars_to_resolution is None
    assert result.resolved_at is None
    assert result.mfe_r == 1.0
    assert result.mae_r == -0.5


def test_outcome_is_causal_to_the_supplied_future_prefix():
    prefix = [candle(100.5, 99.5), candle(101.0, 100.0)]
    baseline = label_signal_outcome(
        event_id="sig_test_causal",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        max_bars=2,
        future_candles=prefix,
    )
    extended = label_signal_outcome(
        event_id="sig_test_causal",
        direction=LONG,
        entry=100.0,
        stop=99.0,
        target_r_multiple=2.0,
        max_bars=2,
        future_candles=prefix + [candle(200.0, 100.0)],
    )

    assert baseline == extended


def test_invalid_stop_and_parameters_fail_fast():
    with pytest.raises(ValueError, match="stop"):
        label_signal_outcome(
            event_id="sig_bad",
            direction=LONG,
            entry=100.0,
            stop=101.0,
            future_candles=[candle(102.0, 100.0)],
        )
    with pytest.raises(ValueError, match="target_r_multiple"):
        label_signal_outcome(
            event_id="sig_bad",
            direction=LONG,
            entry=100.0,
            stop=99.0,
            target_r_multiple=0,
            future_candles=[candle(101.0, 100.0)],
        )


def test_non_finite_trade_parameters_fail_fast():
    with pytest.raises(ValueError, match="entry"):
        label_signal_outcome(
            event_id="sig_bad_entry",
            direction=LONG,
            entry=float("nan"),
            stop=99.0,
            future_candles=[candle(101.0, 100.0)],
        )
    with pytest.raises(ValueError, match="stop"):
        label_signal_outcome(
            event_id="sig_bad_stop",
            direction=LONG,
            entry=100.0,
            stop=float("inf"),
            future_candles=[candle(101.0, 100.0)],
        )
    with pytest.raises(ValueError, match="target_r_multiple"):
        label_signal_outcome(
            event_id="sig_bad_target",
            direction=LONG,
            entry=100.0,
            stop=99.0,
            target_r_multiple=float("nan"),
            future_candles=[candle(101.0, 100.0)],
        )


def test_non_finite_future_candle_fails_fast():
    with pytest.raises(ValueError, match="finite"):
        label_signal_outcome(
            event_id="sig_bad_candle",
            direction=LONG,
            entry=100.0,
            stop=99.0,
            future_candles=[candle(float("nan"), 99.5)],
        )


def test_max_bars_must_be_an_integer():
    with pytest.raises(ValueError, match="integer"):
        label_signal_outcome(
            event_id="sig_bad_horizon",
            direction=LONG,
            entry=100.0,
            stop=99.0,
            max_bars=2.0,
            future_candles=[candle(101.0, 99.5)],
        )
