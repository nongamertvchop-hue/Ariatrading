from strategy.market_structure import BULLISH, MarketStructure
from strategy.mtf import build_mtf_context
from strategy.scoring import score_setup


def test_high_quality_long_score_is_explainable():
    structure = MarketStructure(BULLISH, (), (), ())
    mtf = build_mtf_context(
        {"15m": structure, "1h": structure, "4h": structure},
        "15m",
    )
    score = score_setup("LONG", 4, structure, "FAKE_BREAKOUT", 20, mtf)
    assert score.total == 75
    assert score.zone == 20
    assert score.structure == 20
    assert score.breakout == 25
    assert score.confirmation == 20
    assert score.mtf == 10
