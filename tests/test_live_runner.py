from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from live.execution_guard import ExecutionJournal
from live.runner import ForexLiveOrchestrator, build_arg_parser
from strategy.forex_risk import ForexSymbolContract
from strategy.realtime import LiveBar


def generate_bars(count=60, start_price=1.1000, trend=0.0001):
    base_time = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)
    bars = []
    p = start_price
    for i in range(count):
        t = base_time + timedelta(minutes=15 * i)
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


def test_orchestrator_rejects_live_mode():
    with pytest.raises(ValueError, match="LIVE is fail-closed"):
        ForexLiveOrchestrator(symbols=["EURUSD"], mode="LIVE")


def test_cli_exposes_only_safe_execution_modes():
    mode_action = next(action for action in build_arg_parser()._actions if action.dest == "mode")
    assert mode_action.choices == ["ALERT_ONLY", "DEMO"]


def test_orchestrator_insufficient_bars(eurusd_contract):
    orchestrator = ForexLiveOrchestrator(symbols=["EURUSD"], mode="ALERT_ONLY")
    bars = generate_bars(count=15)
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

    _ = orchestrator.process_symbol(
        symbol="EURUSD",
        bars=bars,
        bid=1.1000,
        ask=1.1001,
        contract=eurusd_contract,
        equity=10000.0,
    )

    res2 = orchestrator.process_symbol(
        symbol="EURUSD",
        bars=bars,
        bid=1.1000,
        ask=1.1001,
        contract=eurusd_contract,
        equity=10000.0,
    )
    assert res2 is None


def _patch_trade_pipeline(monkeypatch, action="LONG"):
    monkeypatch.setattr(
        "live.runner.evaluate_two_setups",
        lambda candles, timeframe: SimpleNamespace(
            signal=SimpleNamespace(action=action, protection="SAFE", stop_reference=1.0990, score=SimpleNamespace(total=8.0))
        ),
    )
    monkeypatch.setattr(
        "live.runner.check_forex_conditions",
        lambda **kwargs: SimpleNamespace(allowed=True, reason="ok", current_session="LONDON"),
    )
    monkeypatch.setattr(
        "live.runner.evaluate_forex_risk",
        lambda **kwargs: SimpleNamespace(allowed=True, reason="ok", lot_size=0.01, risk_amount=10.0),
    )


class _Notifier:
    def __init__(self):
        self.events = []

    def notify_signal(self, **kwargs):
        self.events.append(("signal", kwargs))

    def notify_execution(self, **kwargs):
        self.events.append(("execution", kwargs))

    def notify_rejection(self, **kwargs):
        self.events.append(("rejection", kwargs))

    def notify_system(self, **kwargs):
        self.events.append(("system", kwargs))


def test_demo_execution_is_journaled_and_duplicate_is_suppressed(monkeypatch, tmp_path, eurusd_contract):
    _patch_trade_pipeline(monkeypatch)
    notifier = _Notifier()

    class _Executor:
        def __init__(self):
            self.calls = 0

        def send_market_order(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(success=True, ticket=42, price=1.1001, volume=0.01, comment="ok", retcode=10009)

    executor = _Executor()
    journal = ExecutionJournal(tmp_path / "execution.json")
    orchestrator = ForexLiveOrchestrator(
        symbols=["EURUSD"], mode="DEMO", executor=executor, notifier=notifier, execution_journal=journal
    )
    bars = generate_bars(count=50)

    orchestrator.process_symbol("EURUSD", bars, 1.1000, 1.1001, eurusd_contract, 10000.0)
    # A new orchestrator simulates a process restart with the same durable journal.
    restarted = ForexLiveOrchestrator(
        symbols=["EURUSD"], mode="DEMO", executor=executor, notifier=notifier, execution_journal=journal
    )
    restarted.process_symbol("EURUSD", bars, 1.1000, 1.1001, eurusd_contract, 10000.0)

    assert executor.calls == 1
    assert len(journal.recoverable_intents()) == 0


def test_demo_transport_exception_becomes_ambiguous(monkeypatch, tmp_path, eurusd_contract):
    _patch_trade_pipeline(monkeypatch)
    notifier = _Notifier()

    class _Executor:
        def send_market_order(self, **kwargs):
            raise TimeoutError("broker request timed out")

    journal = ExecutionJournal(tmp_path / "execution.json")
    orchestrator = ForexLiveOrchestrator(
        symbols=["EURUSD"], mode="DEMO", executor=_Executor(), notifier=notifier, execution_journal=journal
    )
    bars = generate_bars(count=50)
    orchestrator.process_symbol("EURUSD", bars, 1.1000, 1.1001, eurusd_contract, 10000.0)

    intents = journal.recoverable_intents()
    assert len(intents) == 1
    assert intents[0]["state"] == "AMBIGUOUS"
    assert any(event[0] == "system" and event[1]["title"] == "Demo Order Ambiguous" for event in notifier.events)
