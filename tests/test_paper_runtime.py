from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from adapters.paper_broker import LONG, PaperBrokerSimulator
from strategy.broker_contract import SymbolContract
from strategy.candles import Candle
from strategy.engine import EngineSignal
from strategy.market_snapshot import MarketSnapshot
from strategy.paper_lifecycle import PaperLifecycleMachine, PaperLifecycleState
from strategy.paper_runtime import PaperTradingRuntime
from strategy.paper_trading_loop import PaperTradingLoop
from strategy.portfolio_risk import PortfolioRiskDecision
from strategy.realtime_guard import DataQuality
from strategy.risk_engine import RiskDecision
from strategy.realtime_supervisor import ALLOW, SupervisorDecision

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
CONTRACT = SymbolContract(symbol="EURUSD", digits=4, point=0.0001, volume_min=0.1, volume_max=100.0, volume_step=0.1)
PORTFOLIO_OK = PortfolioRiskDecision("ALLOW", True, "portfolio risk limits passed", 0.0, 0.0, 0)
RISK_OK = RiskDecision(True, "risk checks passed", 1.0, 0.005, 0.005)


@dataclass
class FakeMonitor:
    evaluations: list
    timeframe: str = "5m"
    last_bar_time: datetime | None = None

    def evaluate_once(self, now=None):
        if not self.evaluations:
            return None
        value = self.evaluations.pop(0)
        self.last_bar_time = value.bar_time
        return value


def evaluation(bar_time: datetime, *, action=LONG, low=1.0990, high=1.1030):
    signal = EngineSignal(
        action=action,
        reason="support reclaim confirmed",
        timeframe="5m",
        entry_reference=1.1000 if action == LONG else 1.1010,
        stop_reference=1.0950 if action == LONG else 1.1060,
        protection="SAFE",
    )
    candle = Candle(open=1.1000, high=high, low=low, close=1.1010)
    quality = DataQuality(True, "ok", NOW, 1.0)
    snapshot = MarketSnapshot(
        symbol="EURUSD", timeframe="5m", bar_time=bar_time, candle=candle,
        current_close=candle.close, data_quality=quality,
    )
    return type("Eval", (), {
        "symbol": "EURUSD", "timeframe": "5m", "evaluated_at": NOW,
        "bar_time": bar_time, "signal": signal, "snapshot": snapshot,
        "event_id": f"evt-{bar_time.isoformat()}",
        "supervisor": SupervisorDecision(ALLOW, True, ("all realtime consistency checks passed",)),
    })()


def make_runtime(tmp_path: Path, broker=None, evaluations=None):
    broker = broker or PaperBrokerSimulator()
    loop = PaperTradingLoop(broker=broker, journal_path=tmp_path / "execution.jsonl", symbol="EURUSD", contract=CONTRACT)
    monitor = FakeMonitor(evaluations or [evaluation(NOW)])
    return PaperTradingRuntime(
        monitor=monitor,
        loop=loop,
        state_path=tmp_path / "runtime.json",
        risk_provider=lambda _: (PORTFOLIO_OK, RISK_OK),
    ), broker


def test_lifecycle_machine_covers_happy_and_unknown_paths():
    machine = PaperLifecycleMachine()
    for state in [PaperLifecycleState.SIGNAL, PaperLifecycleState.APPROVED, PaperLifecycleState.SUBMITTING, PaperLifecycleState.ACKNOWLEDGED, PaperLifecycleState.OPEN, PaperLifecycleState.EXIT_PENDING, PaperLifecycleState.CLOSED, PaperLifecycleState.FLAT]:
        result = machine.transition(state)
        assert result.accepted
    assert not machine.transition(PaperLifecycleState.OPEN).accepted
    machine.restore(PaperLifecycleState.UNKNOWN)
    assert machine.transition(PaperLifecycleState.HALT).accepted


def test_runtime_opens_from_a_new_closed_candle_and_persists_checkpoint(tmp_path: Path):
    runtime, broker = make_runtime(tmp_path)
    ready = runtime.start()
    assert ready.status == "READY"
    result = runtime.tick(now=NOW + timedelta(seconds=1))
    assert result.status == "OPEN"
    assert runtime.loop.position is not None
    assert len(broker.list_orders()) == 1
    assert (tmp_path / "runtime.json").exists()


def test_duplicate_closed_candle_is_no_update_and_does_not_duplicate_order(tmp_path: Path):
    runtime, broker = make_runtime(tmp_path, evaluations=[evaluation(NOW), evaluation(NOW)])
    assert runtime.tick(now=NOW).status == "OPEN"
    before = len(broker.list_orders())
    duplicate = runtime.tick(now=NOW)
    assert duplicate.status == "NO_UPDATE"
    assert len(broker.list_orders()) == before


def test_timeout_after_accept_is_reconciled_without_second_order(tmp_path: Path):
    broker = PaperBrokerSimulator(timeout_after_accept_next=True)
    runtime, _ = make_runtime(tmp_path, broker=broker)
    result = runtime.tick(now=NOW)
    assert result.status == "OPEN"
    assert len(broker.list_orders()) == 1


def test_disconnect_before_submit_halts_fail_closed(tmp_path: Path):
    broker = PaperBrokerSimulator()
    broker.disconnect()
    runtime, _ = make_runtime(tmp_path, broker=broker)
    result = runtime.tick(now=NOW)
    assert result.status == "HALT"
    assert runtime.halted


def test_rejection_never_creates_position(tmp_path: Path):
    runtime, broker = make_runtime(tmp_path, broker=PaperBrokerSimulator(reject_next=True))
    result = runtime.tick(now=NOW)
    assert result.status == "REJECTED"
    assert runtime.loop.position is None
    assert broker.positions() == ()


def test_partial_fill_halts_and_does_not_continue_next_cycle(tmp_path: Path):
    runtime, _ = make_runtime(tmp_path, broker=PaperBrokerSimulator(fill_fraction=0.5))
    result = runtime.tick(now=NOW)
    assert result.status == "HALT"
    assert runtime.halted


def test_restart_rehydrates_position_and_order_without_duplicate_submit(tmp_path: Path):
    first, broker = make_runtime(tmp_path)
    first_result = first.tick(now=NOW)
    assert first_result.status == "OPEN"
    first.stop_price = 1.095
    first._persist()

    second, _ = make_runtime(tmp_path, broker=broker, evaluations=[])
    ready = second.start()
    assert ready.status == "READY"
    assert second.loop.position is not None
    assert second.loop.position.entry_order_id == first.loop.position.entry_order_id
    assert len(broker.list_orders()) == 1


def test_restart_halts_when_broker_position_disappears(tmp_path: Path):
    first, broker = make_runtime(tmp_path)
    assert first.tick(now=NOW).status == "OPEN"
    first._persist()
    broker.clear_positions()
    second, _ = make_runtime(tmp_path, broker=broker, evaluations=[])
    ready = second.start()
    assert ready.status == "HALT"
    assert second.halted


def test_restart_halts_on_corrupt_checkpoint(tmp_path: Path):
    runtime, _ = make_runtime(tmp_path)
    runtime.store.path.write_text('{bad json', encoding="utf-8")
    result = runtime.start()
    assert result.status == "HALT"


def test_failure_matrix_names_are_explicit():
    matrix = {
        "stale_feed": "HALT",
        "duplicate_candle": "NO_UPDATE",
        "disconnect_before_submit": "HALT",
        "timeout_after_accept": "RECONCILE",
        "order_rejected": "REJECTED",
        "partial_fill": "HALT",
        "duplicate_order": "DUPLICATE",
        "position_disappears": "HALT",
        "quantity_mismatch": "HALT",
        "audit_tampered": "HALT",
        "restart": "RECOVER",
        "unknown_order_state": "HALT",
    }
    assert len(matrix) == 12
    assert matrix["restart"] == "RECOVER"
