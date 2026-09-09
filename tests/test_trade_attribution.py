from datetime import datetime, timezone

import pytest

from strategy.engine import EngineSignal, LONG
from strategy.journal import PaperTradeJournal
from strategy.paper import PaperTradingEngine
from strategy.trade_attribution import PaperTradeAttribution
from strategy.candles import Candle
from strategy.levels_v2 import PriceZone, SUPPORT


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def signal_zone() -> PriceZone:
    return PriceZone(low=99.0, high=100.0, kind=SUPPORT, touches=3)


def build_closed_trade():
    journal = PaperTradeJournal()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=signal_zone())
    signal_event = journal.record_signal(
        event_time=dt(1),
        symbol="EURUSD",
        timeframe="1m",
        signal=signal,
        event_id="sig_test_001",
    )
    paper = PaperTradingEngine(reward_risk=1.0)
    position = paper.open_from_signal(
        signal,
        signal_time=dt(1),
        entry_time=dt(2),
        entry_price=101.0,
        signal_event_id=signal_event.event_id,
    )
    assert position is not None
    journal.record_open(
        event_time=position.entry_time,
        symbol="EURUSD",
        timeframe="1m",
        position=position,
    )
    closed = paper.on_bar({"time": dt(3), "high": 104.0, "low": 101.0})
    assert closed is not None
    journal.record_close(
        event_time=closed.exit_time,
        symbol="EURUSD",
        timeframe="1m",
        position=closed,
    )
    return journal


def test_trade_attribution_links_signal_open_and_close():
    attribution = PaperTradeAttribution(build_closed_trade())
    trade = attribution.for_trade(1)

    assert trade is not None
    assert trade.signal is not None
    assert trade.signal.event_id == "sig_test_001"
    assert trade.open_event is not None
    assert trade.open_event.signal_event_id == "sig_test_001"
    assert trade.close_event is not None
    assert trade.close_event.signal_event_id == "sig_test_001"
    assert trade.signal_event_id == "sig_test_001"
    assert trade.outcome == "WIN"
    assert trade.r_multiple == 1.0
    assert trade.is_closed


def test_lookup_by_signal_event_id_returns_matching_trade():
    attribution = PaperTradeAttribution(build_closed_trade())

    matches = attribution.by_signal_event_id("sig_test_001")

    assert len(matches) == 1
    assert matches[0].trade_id == 1


def test_all_trades_can_filter_open_and_closed():
    attribution = PaperTradeAttribution(build_closed_trade())

    assert [item.trade_id for item in attribution.all_trades()] == [1]
    assert [item.trade_id for item in attribution.all_trades(closed_only=True)] == [1]


def test_legacy_trade_without_signal_identity_is_reported_unattributed():
    journal = PaperTradeJournal()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=signal_zone())
    paper = PaperTradingEngine(reward_risk=1.0)
    position = paper.open_from_signal(
        signal,
        signal_time=dt(1),
        entry_time=dt(2),
        entry_price=101.0,
    )
    assert position is not None
    journal.record_open(
        event_time=position.entry_time,
        symbol="EURUSD",
        timeframe="1m",
        position=position,
    )

    attribution = PaperTradeAttribution(journal)
    trade = attribution.for_trade(1)

    assert trade is not None
    assert trade.signal_event_id is None
    assert attribution.unattributed_trades() == (trade,)


def test_conflicting_signal_ids_in_one_trade_fail_closed():
    journal = PaperTradeJournal()
    signal = EngineSignal(LONG, "confirmed", "1m", zone=signal_zone())
    paper = PaperTradingEngine()
    position = paper.open_from_signal(
        signal,
        signal_time=dt(1),
        entry_time=dt(2),
        entry_price=101.0,
        signal_event_id="sig_a",
    )
    assert position is not None
    journal.record_open(
        event_time=dt(2),
        symbol="EURUSD",
        timeframe="1m",
        position=position,
    )

    conflicting = position.__class__(
        **{**position.__dict__, "signal_event_id": "sig_b"},
    )
    conflicting_closed = conflicting.__class__(
        **{**conflicting.__dict__, "status": "CLOSED", "exit_time": dt(3), "exit_price": 102.0, "outcome": "WIN", "r_multiple": 1.0, "bars_held": 1},
    )
    journal.record_close(
        event_time=dt(3),
        symbol="EURUSD",
        timeframe="1m",
        position=conflicting_closed,
    )

    attribution = PaperTradeAttribution(journal)
    with pytest.raises(ValueError, match="conflicting signal_event_id"):
        attribution.for_trade(1)
