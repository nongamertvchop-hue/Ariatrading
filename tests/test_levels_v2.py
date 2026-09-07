import pytest

from strategy.levels_v2 import (
    RESISTANCE,
    SUPPORT,
    build_zones,
    confirmed_swing_lows,
    find_support_zones,
)


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

    assert swings == []


def test_nearby_swings_are_not_counted_as_independent_reactions():
    candles = [
        _c(1.0, 1.01, 0.9990, 1.0050),
        _c(1.0050, 1.0060, 0.9980, 1.0040),
        _c(1.0040, 1.0050, 0.9970, 1.0030),
        _c(1.0030, 1.0040, 0.9985, 1.0020),
        _c(1.0020, 1.0040, 0.9990, 1.0030),
        _c(1.0030, 1.0060, 1.0000, 1.0050),
        _c(1.0050, 1.0070, 1.0010, 1.0060),
        _c(1.0060, 1.0080, 1.0020, 1.0070),
        _c(1.0070, 1.0080, 1.0005, 1.0060),
        _c(1.0060, 1.0070, 1.0015, 1.0050),
        _c(1.0050, 1.0060, 1.0020, 1.0040),
    ]

    zones = find_support_zones(
        candles,
        strength=1,
        tolerance=0.0020,
        min_touches=2,
        min_reaction_gap=3,
    )

    assert zones
    assert zones[0].touches == 2


def test_reaction_gap_can_block_a_zone_with_only_clustered_swings():
    candles = [
        _c(1.0, 1.01, 0.999, 1.005),
        _c(1.005, 1.006, 0.998, 1.004),
        _c(1.004, 1.005, 0.997, 1.003),
        _c(1.003, 1.004, 0.998, 1.002),
        _c(1.002, 1.004, 0.999, 1.003),
        _c(1.003, 1.006, 1.000, 1.005),
    ]

    zones = find_support_zones(
        candles,
        strength=1,
        tolerance=0.0020,
        min_touches=2,
        min_reaction_gap=10,
    )

    assert zones == []
