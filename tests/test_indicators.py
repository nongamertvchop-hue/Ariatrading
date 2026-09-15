from strategy.indicators import (
    adx,
    atr,
    calculate_indicators,
    ema,
    macd,
    rsi,
    true_range_series,
)


def candles_from_closes(closes: list[float]) -> list[dict[str, float]]:
    return [
        {"open": close - 0.1, "high": close + 0.2, "low": close - 0.2, "close": close}
        for close in closes
    ]


def test_ema_uses_sma_seed_and_is_causal() -> None:
    candles = candles_from_closes([1.0, 2.0, 3.0, 4.0])
    assert ema(candles, 3) == 3.0

    prefix = candles[:3]
    extended = candles + candles_from_closes([100.0])
    assert ema(prefix, 3) == ema(extended[:3], 3)


def test_rsi_handles_flat_and_one_direction_series() -> None:
    flat = candles_from_closes([10.0] * 20)
    rising = candles_from_closes([float(index) for index in range(1, 21)])
    falling = candles_from_closes([float(21 - index) for index in range(1, 21)])

    assert rsi(flat, 14) == 50.0
    assert rsi(rising, 14) == 100.0
    assert rsi(falling, 14) == 0.0


def test_true_range_uses_previous_close_for_gaps() -> None:
    candles = [
        {"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0},
        {"open": 15.0, "high": 16.0, "low": 14.0, "close": 15.0},
    ]
    assert true_range_series(candles) == [3.0, 5.0]


def test_atr_is_unavailable_before_warmup() -> None:
    candles = candles_from_closes([float(index) for index in range(20)])
    assert atr(candles[:13], 14) is None
    assert atr(candles[:14], 14) == 0.4


def test_adx_is_unavailable_until_directional_warmup() -> None:
    candles = candles_from_closes([float(index) for index in range(1, 30)])
    assert adx(candles[:26], 14) is None
    assert adx(candles[:27], 14) is not None
    assert adx(candles, 14) is not None


def test_macd_requires_slow_and_signal_warmup() -> None:
    short = candles_from_closes([float(index) for index in range(40)])
    line, signal, histogram = macd(short)
    assert line is not None
    assert signal is not None
    assert histogram is not None

    shorter = candles_from_closes([float(index) for index in range(30)])
    assert macd(shorter)[1] is None


def test_default_snapshot_is_deterministic_and_has_expected_warmups() -> None:
    candles = candles_from_closes([float(index) for index in range(1, 220)])
    first = calculate_indicators(candles)
    second = calculate_indicators(candles)
    assert first == second
    assert first.ema20 is not None
    assert first.ema50 is not None
    assert first.ema200 is not None
    assert first.rsi14 is not None
    assert first.atr14 is not None
    assert first.adx14 is not None
    assert first.macd is not None
    assert first.macd_signal is not None
    assert first.macd_histogram is not None


def test_indicator_calculation_rejects_non_finite_input() -> None:
    candles = candles_from_closes([1.0, 2.0, 3.0])
    candles[-1]["close"] = float("nan")
    try:
        ema(candles, 2)
    except ValueError as exc:
        assert "close must be finite" in str(exc)
    else:
        raise AssertionError("expected ValueError")
