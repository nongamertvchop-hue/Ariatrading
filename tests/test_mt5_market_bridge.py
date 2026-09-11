from types import SimpleNamespace

import pytest

from live import mt5_market_bridge as bridge


class FakeMT5:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def __init__(self, completed, live, tick):
        self.completed = completed
        self.live = live
        self.tick_value = tick

    def symbol_select(self, symbol, enabled):
        assert symbol == "EURUSD"
        assert enabled is True
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        assert symbol == "EURUSD"
        if start_pos == 1:
            return self.completed[:count]
        if start_pos == 0:
            return self.live[:count]
        raise AssertionError(start_pos)

    def symbol_info_tick(self, symbol):
        assert symbol == "EURUSD"
        return self.tick_value

    def last_error(self):
        return "fake error"


@pytest.fixture
def fake(monkeypatch):
    completed = [
        SimpleNamespace(time=1_700_000_000, open=1.1, high=1.2, low=1.0, close=1.15),
        SimpleNamespace(time=1_700_000_900, open=1.15, high=1.25, low=1.1, close=1.2),
    ]
    live = [
        SimpleNamespace(time=1_700_001_800, open=1.2, high=1.3, low=1.15, close=1.27),
    ]
    tick = SimpleNamespace(time=1_700_001_900, bid=1.2698, ask=1.2700)
    fake_mt5 = FakeMT5(completed, live, tick)
    monkeypatch.setattr(bridge, "mt5", fake_mt5)
    monkeypatch.setitem(bridge.TIMEFRAME_MAP, "15m", fake_mt5.TIMEFRAME_M15)
    return completed, live, tick


def test_market_payload_separates_completed_and_live_candles(fake):
    completed, live, tick = fake
    payload = bridge.market_payload("EURUSD", "15m", 100)
    assert payload["source"] == "mt5"
    assert payload["execution"] == "NONE"
    assert len(payload["candles"]) == len(completed)
    assert payload["candles"][-1]["time"] == completed[-1].time
    assert payload["live_candle"]["time"] == live[0].time
    assert payload["live_candle"]["close"] == live[0].close
    assert payload["price"] == pytest.approx((tick.bid + tick.ask) / 2)


def test_market_payload_rejects_invalid_tick(fake, monkeypatch):
    _completed, _live, _tick = fake
    monkeypatch.setattr(bridge.mt5, "symbol_info_tick", lambda _symbol: SimpleNamespace(time=1, bid=0.0, ask=0.0))
    with pytest.raises(RuntimeError, match="tick is invalid"):
        bridge.market_payload("EURUSD", "15m", 100)
