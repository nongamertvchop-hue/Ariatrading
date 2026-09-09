from datetime import datetime, timezone
import json

import pytest

from strategy.engine import EngineSignal, LONG
from strategy.journal import JournalEvent, PaperTradeJournal
from strategy.levels_v2 import PriceZone, SUPPORT
from strategy.paper import PaperTradingEngine
from strategy.performance import PaperPerformanceAnalyzer
from strategy.trade_attribution import TradeAttribution


def dt(minute: int) -> datetime:
    return datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc)


def signal(event_id: str) -> JournalEvent:
    return JournalEvent(
        event_time=dt(1), event_type="SIGNAL", symbol="EURUSD", timeframe="1m",
        action="LONG", reason="confirmed", event_id=event_id,
    )


def trade(trade_id: int, event_id: str, r_multiple: float, bars_held: int = 2) -> TradeAttribution:
    source = signal(event_id)
    opened = JournalEvent(
        event_time=dt(2), event_type="OPEN", symbol="EURUSD", timeframe="1m",
        action="LONG", reason="paper position opened", trade_id=trade_id,
        entry_price=100.0, stop=99.0, target=102.0, signal_event_id=event_id,
    )
    closed = JournalEvent(
        event_time=dt(2 + bars_held), event_type="CLOSE", symbol="EURUSD", timeframe="1m",
        action="LONG", reason="paper position closed", trade_id=trade_id,
        entry_price=100.0, stop=99.0, target=102.0,
        exit_price=102.0 if r_multiple > 0 else 99.0,
        outcome="WIN" if r_multiple > 0 else "LOSS", r_multiple=r_multiple,
        bars_held=bars_held, signal_event_id=event_id,
    )
    return TradeAttribution(trade_id, source, opened, closed)


def test_report_calculates_r_metrics_and_drawdown():
    report = PaperPerformanceAnalyzer([
        trade(1, "sig_a", 2.0), trade(2, "sig_b", -1.0),
        trade(3, "sig_c", 0.0), trade(4, "sig_d", 1.0),
    ]).report()
    assert report.total_trades == 4
    assert report.wins == 2
    assert report.losses == 1
    assert report.breakeven == 1
    assert report.win_rate == 0.5
    assert report.gross_r == 2.0
    assert report.average_r == 0.5
    assert report.expectancy_r == 0.5
    assert report.profit_factor == 3.0
    assert report.max_drawdown_r == 1.0
    assert report.average_bars_held == 2.0
    assert report.r_stddev == pytest.approx(1.11803398875)


def test_empty_report_is_safe_and_deterministic():
    report = PaperPerformanceAnalyzer([]).report()
    assert report.total_trades == 0
    assert report.win_rate == 0.0
    assert report.gross_r == 0.0
    assert report.average_r == 0.0
    assert report.profit_factor is None
    assert report.max_drawdown_r == 0.0
    assert report.average_bars_held == 0.0
    assert report.r_stddev == 0.0


def test_positive_only_profit_factor_is_infinite_and_serializes_safely():
    report = PaperPerformanceAnalyzer([trade(1, "sig_a", 1.5)]).report()
    assert report.profit_factor == float("inf")
    payload = report.as_dict()
    assert payload["profit_factor"] is None
    assert payload["profit_factor_unbounded"] is True
    json.dumps(payload, allow_nan=False)


def test_non_finite_r_is_rejected():
    with pytest.raises(ValueError, match="r_multiple must be finite"):
        PaperPerformanceAnalyzer([trade(1, "sig_a", float("nan"))]).report()


def test_closed_trade_filter_is_applied_before_metrics():
    open_trade = TradeAttribution(
        2, signal("sig_b"),
        JournalEvent(
            event_time=dt(2), event_type="OPEN", symbol="EURUSD", timeframe="1m",
            action="LONG", reason="paper position opened", trade_id=2,
            entry_price=100.0, stop=99.0, target=102.0, signal_event_id="sig_b",
        ),
        None,
    )
    report = PaperPerformanceAnalyzer([trade(1, "sig_a", 2.0), open_trade]).report()
    assert report.total_trades == 1
    assert report.gross_r == 2.0


def test_by_outcome_returns_stable_grouped_reports():
    grouped = PaperPerformanceAnalyzer([
        trade(1, "sig_a", 2.0), trade(2, "sig_b", -1.0), trade(3, "sig_c", 1.0),
    ]).by_outcome()
    assert list(grouped) == ["LOSS", "WIN"]
    assert grouped["WIN"].total_trades == 2
    assert grouped["WIN"].gross_r == 3.0
    assert grouped["LOSS"].total_trades == 1
    assert grouped["LOSS"].gross_r == -1.0


def test_from_journal_builds_analyzer_from_public_journal_api():
    journal = PaperTradeJournal()
    source_signal = EngineSignal(
        LONG,
        "confirmed",
        "1m",
        zone=PriceZone(low=99.0, high=100.0, kind=SUPPORT, touches=3),
    )
    source = journal.record_signal(
        event_time=dt(1),
        symbol="EURUSD",
        timeframe="1m",
        signal=source_signal,
        event_id="sig_a",
    )
    paper = PaperTradingEngine(reward_risk=1.0)
    position = paper.open_from_signal(
        source_signal,
        signal_time=dt(1),
        entry_time=dt(2),
        entry_price=101.0,
        signal_event_id=source.event_id,
    )
    assert position is not None
    journal.record_open(event_time=dt(2), symbol="EURUSD", timeframe="1m", position=position)
    closed = paper.on_bar({"time": dt(3), "high": 103.0, "low": 101.0})
    assert closed is not None
    journal.record_close(event_time=closed.exit_time, symbol="EURUSD", timeframe="1m", position=closed)

    report = PaperPerformanceAnalyzer.from_journal(journal).report()
    assert report.total_trades == 1
    assert report.gross_r == 1.0
