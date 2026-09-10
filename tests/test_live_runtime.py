from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.execution_guard import ExecutionJournal
from live.mt5_executor import AccountIdentity


class _Executor:
    def __init__(self, tick_time, deals=None, *, broker_evidence=None, login=1, server="DemoServer", company="DemoBroker", trade_mode=2):
        self.tick_time = tick_time
        self.deals = deals or []
        self.broker_evidence = broker_evidence or {}
        self.login = login
        self.server = server
        self.company = company
        self.trade_mode = trade_mode
        self.magic_number = 8808
        self.bound_identity = None
        self.mt5 = SimpleNamespace(
            account_info=lambda: SimpleNamespace(
                login=self.login,
                server=self.server,
                company=self.company,
                trade_mode=self.trade_mode,
                trade_allowed=True,
                trade_expert=True,
            ),
            last_error=lambda: (0, "ok"),
            DEAL_ENTRY_OUT=1,
            DEAL_ENTRY_OUT_BY=3,
            DEAL_TYPE_BUY=0,
            DEAL_TYPE_SELL=1,
            ORDER_TYPE_BUY=0,
            ORDER_TYPE_SELL=1,
            history_deals_get=lambda start, end: self.deals,
            positions_get=lambda symbol=None: self.broker_evidence.get("positions", []),
            history_orders_get=lambda start, end: self.broker_evidence.get("orders", []),
        )

    def get_account_identity(self):
        return AccountIdentity(
            login=self.login,
            server=self.server,
            company=self.company,
            trade_mode=self.trade_mode,
        )

    def bind_account_identity(self, identity):
        if self.get_account_identity() != identity:
            raise RuntimeError("identity mismatch")
        if self.bound_identity is not None and self.bound_identity != identity:
            raise RuntimeError("identity already bound")
        self.bound_identity = identity

    def get_account_snapshot(self):
        return SimpleNamespace(login=self.login, equity=10000.0, trade_allowed=True, trade_expert=True)

    def get_open_positions(self):
        return []

    def get_current_tick(self, symbol):
        return 1.10000, 1.10010, self.tick_time

    def get_symbol_contract(self, symbol):
        return SimpleNamespace(point=0.00001)


class _Feed:
    def __init__(self, bar_time):
        self.bar_time = bar_time

    def closed_bars(self, symbol, timeframe, count):
        return [SimpleNamespace(time=self.bar_time, open=1.1, high=1.101, low=1.099, close=1.1005)] * 40


class _Orchestrator:
    mode = "LIVE"
    timeframe = "15m"
    candle_history = 50
    symbols = ["EURUSD"]

    def __init__(self):
        self.calls = 0
        self.kwargs = None

    def process_symbol(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs


def _runtime(tmp_path, *, now=None, tick_time=None, bar_time=None, deals=None, limits=None, login=1):
    now = now or datetime.now(timezone.utc)
    orchestrator = _Orchestrator()
    executor = _Executor(tick_time if tick_time is not None else now, deals=deals, login=login)
    runtime = LiveRuntime(
        orchestrator=orchestrator,
        feed=_Feed(bar_time if bar_time is not None else now - timedelta(seconds=1)),
        executor=executor,
        journal=ExecutionJournal(tmp_path / "execution.json"),
        limits=limits,
        clock=lambda: now,
    )
    runtime.preflight = lambda: None
    runtime._bound_account_identity = executor.get_account_identity()
    return runtime, orchestrator


def test_daily_circuit_breaker_persists_and_blocks(tmp_path):
    breaker = DailyCircuitBreaker(tmp_path / "breaker.json", 0.02)
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert breaker.check(10000.0, now)[0]
    ok, reason = breaker.check(9800.0, now)
    assert not ok
    assert "daily drawdown" in reason
    ok, reason = breaker.check(9799.0, now)
    assert not ok
    assert "daily drawdown" in reason


def test_runtime_preflight_blocks_unreconciled_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    journal = ExecutionJournal(tmp_path / "execution.json")
    from live.execution_guard import build_intent
    intent = build_intent(
        symbol="EURUSD", direction="BUY", bar_time=datetime(2026, 9, 10, tzinfo=timezone.utc),
        entry=1.1, sl=1.099, tp=1.102, lot_size=0.01,
    )
    journal.reserve(intent)
    runtime = LiveRuntime(
        orchestrator=_Orchestrator(), feed=_Feed(datetime.now(timezone.utc)),
        executor=_Executor(datetime.now(timezone.utc)), journal=journal,
        clock=lambda: datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )
    with pytest.raises(RuntimeError, match="unreconciled"):
        runtime.preflight()


def test_runtime_reconciles_exact_broker_evidence(tmp_path):
    from live.execution_guard import build_intent
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    intent = build_intent(
        symbol="EURUSD", direction="BUY", bar_time=datetime(2026, 9, 10, 11, tzinfo=timezone.utc),
        entry=1.1, sl=1.099, tp=1.102, lot_size=0.01,
    )
    journal = ExecutionJournal(tmp_path / "execution.json")
    journal.reserve(intent)
    journal.transition(intent.intent_id, "AMBIGUOUS", error="transport timeout")
    evidence = {
        "orders": [SimpleNamespace(
            magic=8808, symbol="EURUSD", comment=f"Aria-{intent.intent_id[:12]}",
            type=0, volume_initial=0.01, ticket=9001, position_id=9002,
        )],
        "positions": [],
    }
    runtime = LiveRuntime(
        orchestrator=_Orchestrator(), feed=_Feed(now),
        executor=_Executor(now, broker_evidence=evidence), journal=journal,
        clock=lambda: now,
    )
    assert runtime._reconcile_unresolved(now) == 1
    assert journal.get(intent.intent_id)["state"] == "SUCCEEDED"


def test_runtime_does_not_reconcile_weak_or_foreign_evidence(tmp_path):
    from live.execution_guard import build_intent
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    intent = build_intent(
        symbol="EURUSD", direction="BUY", bar_time=datetime(2026, 9, 10, 11, tzinfo=timezone.utc),
        entry=1.1, sl=1.099, tp=1.102, lot_size=0.01,
    )
    journal = ExecutionJournal(tmp_path / "execution.json")
    journal.reserve(intent)
    journal.transition(intent.intent_id, "AMBIGUOUS", error="transport timeout")
    evidence = {
        "orders": [SimpleNamespace(
            magic=1234, symbol="EURUSD", comment=f"Aria-{intent.intent_id[:12]}",
            type=0, volume_initial=0.01, ticket=9001, position_id=9002,
        )],
        "positions": [],
    }
    runtime = LiveRuntime(
        orchestrator=_Orchestrator(), feed=_Feed(now),
        executor=_Executor(now, broker_evidence=evidence), journal=journal,
        clock=lambda: now,
    )
    assert runtime._reconcile_unresolved(now) == 0
    assert journal.get(intent.intent_id)["state"] == "AMBIGUOUS"


def test_runtime_skips_stale_tick(tmp_path):
    now = datetime.now(timezone.utc)
    runtime, orchestrator = _runtime(
        tmp_path, now=now, tick_time=now - timedelta(seconds=30),
        bar_time=now - timedelta(minutes=1), limits=RuntimeLimits(max_tick_age_seconds=10.0),
    )
    assert runtime.process_once() == 0
    assert orchestrator.calls == 0


def test_runtime_skips_future_tick(tmp_path):
    now = datetime.now(timezone.utc)
    runtime, orchestrator = _runtime(tmp_path, now=now, tick_time=now + timedelta(seconds=1))
    assert runtime.process_once() == 0
    assert orchestrator.calls == 0


def test_runtime_skips_future_candle(tmp_path):
    now = datetime.now(timezone.utc)
    runtime, orchestrator = _runtime(tmp_path, now=now, bar_time=now + timedelta(seconds=1))
    assert runtime.process_once() == 0
    assert orchestrator.calls == 0


def test_runtime_forwards_realized_loss_to_strategy_boundary(tmp_path):
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    deals = [
        SimpleNamespace(magic=8808, entry=1, profit=-75.0, swap=-2.0, commission=-3.0),
        SimpleNamespace(magic=1234, entry=1, profit=-999.0, swap=0.0, commission=0.0),
        SimpleNamespace(magic=8808, entry=0, profit=-50.0, swap=0.0, commission=0.0),
    ]
    runtime, orchestrator = _runtime(tmp_path, now=now, deals=deals)
    assert runtime.process_once() == 1
    assert orchestrator.kwargs["daily_realized_loss"] == 80.0


def test_runtime_rejects_naive_tick_timestamp(tmp_path):
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    runtime, _ = _runtime(tmp_path, now=now, tick_time=datetime(2026, 9, 10, 12))
    with pytest.raises(RuntimeError, match="tick timestamp must be timezone-aware"):
        runtime.process_once()


def test_runtime_blocks_account_switch_after_preflight(tmp_path):
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    runtime, orchestrator = _runtime(tmp_path, now=now, login=1)
    runtime.executor.login = 2

    with pytest.raises(RuntimeError, match="account identity changed during runtime"):
        runtime.process_once()
    assert orchestrator.calls == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("server", "OtherDemoServer"),
        ("company", "OtherBroker"),
        ("trade_mode", 0),
    ],
)
def test_runtime_blocks_non_login_account_identity_drift(tmp_path, field, value):
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    runtime, orchestrator = _runtime(tmp_path, now=now)
    setattr(runtime.executor, field, value)

    with pytest.raises(RuntimeError, match="account identity changed during runtime"):
        runtime.process_once()
    assert orchestrator.calls == 0
