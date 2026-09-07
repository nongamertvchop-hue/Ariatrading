from datetime import datetime, timezone
from types import SimpleNamespace

from live.demo_auto_trader import DemoAutoTrader
from strategy.engine import EngineSignal, LONG
from strategy.realtime import LiveEvaluation
from strategy.realtime_supervisor import SupervisorDecision
from strategy.system_gate import SystemGateDecision


class FakeMonitor:
    def __init__(self, evaluation):
        self.evaluation = evaluation

    def evaluate_once(self, now=None):
        return self.evaluation


class FakeExecutor:
    def __init__(self):
        self.mt5 = SimpleNamespace(
            symbol_info_tick=lambda symbol: SimpleNamespace(ask=1.10125, bid=1.10115),
            symbol_info=lambda symbol: SimpleNamespace(),
            last_error=lambda: (0, "ok"),
        )
        self.opened = []

    def positions(self, symbol):
        return ()

    def open_market(self, **kwargs):
        self.opened.append(kwargs)
        return SimpleNamespace(status="FILLED")


def evaluation():
    return LiveEvaluation(
        symbol="EURUSD",
        timeframe="15m",
        evaluated_at=datetime(2026, 9, 7, 8, 15, tzinfo=timezone.utc),
        bar_time=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        signal=EngineSignal(LONG, "test", "15m", protection="SAFE", stop_reference=1.099),
        support=None,
        resistance=None,
        supervisor=SupervisorDecision("ALLOW", True, ("ok",)),
        snapshot=SimpleNamespace(),
    )


def gate(_evaluation):
    return SystemGateDecision("ALLOW", True, "ok", quantity=0.01)


def test_off_control_blocks_order_even_when_all_other_checks_pass():
    executor = FakeExecutor()
    trader = DemoAutoTrader(
        FakeMonitor(evaluation()),
        executor,
        gate_resolver=gate,
        risk_plan_resolver=lambda evaluation, entry: (1.099, 1.105),
        execution_enabled=lambda: False,
    )

    result = trader.process_once()

    assert result is not None
    assert result.action == "SKIP"
    assert "OFF" in result.reason
    assert executor.opened == []


def test_control_is_checked_again_immediately_before_execution():
    executor = FakeExecutor()
    states = iter([True, False])
    trader = DemoAutoTrader(
        FakeMonitor(evaluation()),
        executor,
        gate_resolver=gate,
        risk_plan_resolver=lambda evaluation, entry: (1.099, 1.105),
        execution_enabled=lambda: next(states),
    )

    result = trader.process_once()

    assert result is not None
    assert result.action == "SKIP"
    assert "switched OFF" in result.reason
    assert executor.opened == []
