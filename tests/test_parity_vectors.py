import json
from pathlib import Path

import pytest

from strategy.fake_breakout import classify_resistance_breakout, classify_support_breakout
from strategy.levels_v2 import PriceZone, RESISTANCE, SUPPORT


FIXTURE = Path(__file__).parent / "fixtures" / "parity_vectors.json"


def load_vectors():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", load_vectors()["breakout"], ids=lambda vector: vector["name"])
def test_python_matches_cross_runtime_breakout_contract(vector):
    zone = PriceZone(**vector["zone"])
    candle = vector["candle"]
    from strategy.candles import Candle

    result = (
        classify_support_breakout(Candle(**candle), zone, vector["buffer"])
        if vector["direction"] == "LONG"
        else classify_resistance_breakout(Candle(**candle), zone, vector["buffer"])
    )
    assert result.state == vector["expected_state"]


@pytest.mark.parametrize("vector", load_vectors()["zone_center"], ids=lambda vector: str(vector["expected_center"]))
def test_python_zone_center_golden_contract(vector):
    zone = PriceZone(vector["low"], vector["high"], SUPPORT, 2)
    assert zone.center == pytest.approx(vector["expected_center"])
