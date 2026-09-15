from strategy.engine import LONG, SHORT, _indicator_confirmation
from strategy.indicators import IndicatorSnapshot


def snapshot(
    *,
    ema20: float,
    ema50: float,
    ema200: float | None,
    rsi14: float,
    adx14: float,
    macd_histogram: float,
) -> IndicatorSnapshot:
    return IndicatorSnapshot(
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        rsi14=rsi14,
        atr14=1.0,
        adx14=adx14,
        macd=0.1,
        macd_signal=0.0,
        macd_histogram=macd_histogram,
    )


def test_long_is_confirmed_when_directional_indicators_align():
    confirmed, strength, reasons = _indicator_confirmation(
        LONG,
        snapshot(
            ema20=105.0,
            ema50=100.0,
            ema200=95.0,
            rsi14=58.0,
            adx14=28.0,
            macd_histogram=0.5,
        ),
    )

    assert confirmed is True
    assert strength == 20
    assert all("opposed" not in reason for reason in reasons)


def test_short_is_confirmed_when_directional_indicators_align():
    confirmed, strength, _ = _indicator_confirmation(
        SHORT,
        snapshot(
            ema20=95.0,
            ema50=100.0,
            ema200=105.0,
            rsi14=42.0,
            adx14=24.0,
            macd_histogram=-0.5,
        ),
    )

    assert confirmed is True
    assert strength == 19


def test_long_is_blocked_when_macd_conflicts():
    confirmed, strength, reasons = _indicator_confirmation(
        LONG,
        snapshot(
            ema20=105.0,
            ema50=100.0,
            ema200=95.0,
            rsi14=58.0,
            adx14=28.0,
            macd_histogram=-0.5,
        ),
    )

    assert confirmed is False
    assert strength == 0
    assert "MACD histogram=opposed" in reasons


def test_short_is_blocked_when_rsi_conflicts():
    confirmed, strength, reasons = _indicator_confirmation(
        SHORT,
        snapshot(
            ema20=95.0,
            ema50=100.0,
            ema200=105.0,
            rsi14=57.0,
            adx14=28.0,
            macd_histogram=-0.5,
        ),
    )

    assert confirmed is False
    assert strength == 0
    assert any(reason.startswith("RSI14=57.00 opposed") for reason in reasons)


def test_indicator_warmup_does_not_create_a_direction():
    confirmed, strength, reasons = _indicator_confirmation(
        LONG,
        snapshot(
            ema20=105.0,
            ema50=None,
            ema200=None,
            rsi14=None,
            adx14=None,
            macd_histogram=None,
        ),
    )

    assert confirmed is False
    assert strength == 0
    assert reasons == ("indicator warmup incomplete",)
