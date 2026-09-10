from datetime import datetime, timedelta, timezone

import pytest

from live.mt5_executor import MT5LiveExecutor
from live.notifier import NotificationConfig, Notifier
from live.runner import ForexLiveOrchestrator
from strategy.forex_conditions import ForexSessionConfig
from strategy.forex_risk import ForexSymbolContract
from strategy.realtime import LiveBar
from tests.test_mt5_executor import FakeMT5Module


def generate_bars(count=60, start_price=1.1000, trend=0.0001):
    base_time = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
    bars = []
    p = start_price
    for i in range(count):
        t = base_time + timedelta(minutes=15 * i)
        # Form basic swings
        o = p
        h = p + 0.0005
        l = p - 0.0003
        c = p + trend
        bars.append(LiveBar(time=t, open=o, high=h, low=l, close=c))
        p = c
    return bars


@pytest.fixture
def eurusd_contract():
    return ForexSymbolContract(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        trade_tick_value=1.0,
        trade_tick_size=0.00001,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def test_orchestrator_initialization():
    orchestrator = ForexLiveOrchestrator(
        symbols=["EURUSD", "GBPUSD"],
        mode="ALERT_ONLY",
        timeframe="15m",
        risk_per_trade=0.01,
    )
    assert orchestrator.symbols == ["EURUSD", "GBPUSD"]
    assert orchestrator.mode == "ALERT_ONLY"


def test_orchestrator_insufficient_bars(eurusd_contract):
    orchestrator = ForexLiveOrchestrator(symbols=["EURUSD"], mode="ALERT_ONLY")
    bars = generate_bars(count=15)  # < 30
    res = orchestrator.process_symbol(
        symbol="EURUSD",
        bars=bars,
        bid=1.1000,
        ask=1.1001,
        contract=eurusd_contract,
        equity=10000.0,
    )
    assert res is None


def test_orchestrator_deduplicates_same_bar(eurusd_contract):
    orchestrator = ForexLiveOrchestrator(symbols=["EURUSD"], mode="ALERT_ONLY")
    bars = generate_bars(count=50)

    # First run processes or evaluates
    _ = orchestrator.process_symbol(
        symbol="EURUSD",
        bars=bars,
        bid=1.1000,
        ask=1.1001,
        contract=eurusd_contract,
        equity=10000.0,
    )

    # Second run with exact same bars returns None immediately without recalculating
    res2 = orchestrator.process_symbol(
        symbol="EURUSD",
        bars=bars,
        bid=1.1000,
        ask=1.1001,
        contract=eurusd_contract,
        equity=10000.0,
    )
    assert res2 is None
