from datetime import datetime, timezone

import pytest

import adapters.mt5_feed as mt5_feed


class FakeMT5:
    TIMEFRAME_M1 = 1

    def initialize(self, **kwargs):
        return True

    def shutdown(self):
        return None

    def last_error(self):
        return (0, "ok")

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        return [
            {
                "time": int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()),
                "open": 1.1,
                "high": 1.101,
                "low": 1.099,
                "close": 1.1005,
            }
        ]

    def symbol_info_tick(self, symbol):
        class Tick:
            time = int(datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc).timestamp())
            bid = 1.1
            ask = 1.1001
            last = 1.10005
            volume = 10

        return Tick()


def test_mt5_feed_accepts_injected_module_without_importing_package():
    feed = mt5_feed.MT5BarFeed(FakeMT5())
    bars = feed.closed_bars("EURUSD", "1m", 1)
    assert len(bars) == 1
    assert bars[0].close == pytest.approx(1.1005)
    feed.close()


def test_mt5_feed_gives_clear_error_when_optional_package_is_missing(monkeypatch):
    monkeypatch.setattr(mt5_feed, "mt5", None)

    with pytest.raises(RuntimeError, match="MetaTrader5 package ไม่พร้อมใช้งาน"):
        mt5_feed.MT5BarFeed()


def test_mt5_feed_does_not_hide_dependency_error_as_attribute_error(monkeypatch):
    monkeypatch.setattr(mt5_feed, "mt5", None)

    with pytest.raises(RuntimeError, match="ฟีเจอร์ realtime feed นี้จึงใช้ไม่ได้"):
        mt5_feed._require_mt5()
