from datetime import datetime, timezone

import pytest

from strategy.candles import Candle
from strategy.market_snapshot import MarketSnapshot


def test_market_snapshot_validates_and_serializes_canonical_observation():
    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timeframe="1m",
        bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        candle=Candle(1.10, 1.11, 1.09, 1.105),
        current_close=1.105,
        spread=0.0001,
        latency_seconds=0.25,
    )

    assert snapshot.ready
    data = snapshot.as_dict()
    assert data["symbol"] == "EURUSD"
    assert data["timeframe"] == "1m"
    assert data["close"] == 1.105
    assert data["has_forecast"] is False


def test_market_snapshot_requires_timezone_aware_bar_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketSnapshot(
            symbol="EURUSD",
            timeframe="1m",
            bar_time=datetime(2026, 1, 1),
            candle=Candle(1.10, 1.11, 1.09, 1.105),
            current_close=1.105,
        )


def test_market_snapshot_requires_close_consistency():
    with pytest.raises(ValueError, match="current_close"):
        MarketSnapshot(
            symbol="EURUSD",
            timeframe="1m",
            bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            candle=Candle(1.10, 1.11, 1.09, 1.105),
            current_close=1.104,
        )


def test_market_snapshot_rejects_negative_quality_metadata():
    with pytest.raises(ValueError, match="spread"):
        MarketSnapshot(
            symbol="EURUSD",
            timeframe="1m",
            bar_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            candle=Candle(1.10, 1.11, 1.09, 1.105),
            current_close=1.105,
            spread=-0.0001,
        )
