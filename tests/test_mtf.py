from strategy.market_structure import BULLISH, BEARISH, MarketStructure
from strategy.mtf import build_mtf_context, mtf_direction_score


def structure(bias):
    return MarketStructure(bias, (), (), ())


def test_bullish_mtf_alignment():
    context = build_mtf_context(
        {"15m": structure(BULLISH), "1h": structure(BULLISH), "4h": structure(BULLISH)},
        "15m",
    )
    assert context.alignment == BULLISH
    assert mtf_direction_score("LONG", context) == 10


def test_mixed_mtf_is_not_bullish():
    context = build_mtf_context(
        {"15m": structure(BULLISH), "1h": structure(BEARISH), "4h": structure(BULLISH)},
        "15m",
    )
    assert context.alignment != BULLISH
    assert mtf_direction_score("LONG", context) == 0
