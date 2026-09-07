import pytest

from strategy.levels_v2 import RESISTANCE, SUPPORT, build_zones, confirmed_swing_lows


def _c(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


def test_cluster_does_not_chain_distant_reactions_into_one_zone():
    zones = build_zones(
        [1.1000, 1.1009, 1.1018],
        SUPPORT,
        tolerance=0.0010,
        min_touches=2,
    )

    assert len(zones) == 1
    assert zones[0].touches == 2
    assert zones[0].low == pytest.approx(1.0990)
    assert zones[0].high == pytest.approx(1.1019)


def test_zone_kind_is_preserved_for_resistance():
    zones = build_zones(
        [1.2000, 1.2005],
        RESISTANCE,
        tolerance=0.0010,
        min_touches=2,
    )

    assert len(zones) == 1
    assert zones[0].kind == RESISTANCE
    assert zones[0].touches == 2


def test_confirmed_swing_needs_both_sides_of_confirmation_window():
    candles = [
        _c(1.0, 1.01, 0.99, 1.0),
        _c(1.0, 1.01, 0.98, 0.99),
        _c(0.99, 1.00, 0.97, 0.98),
        _c(0.98, 0.99, 0.975, 0.98),
    ]

    swings = confirmed_swing_lows(candles, strength=2)

    # The candidate at index 2 has only one candle to its right, so it is
    # not confirmed and must not become a tradable historical level yet.
    assert swings == []
