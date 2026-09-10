from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from live.live_runtime import DailyCircuitBreaker, LiveRuntime, RuntimeLimits
from live.execution_guard import ExecutionJournal


class _Executor:
    def __init__(self, tick_time):
        self.tick_time = tick_time
        self.mt5 = SimpleNamespace(
            account_info=lambda: SimpleNamespace(trade_mode=2, trade_allowed=True, trade_expert=True),
            last_error=lambda: (0, "ok"),
        )

    def get_account_snapshot(self):
        return SimpleNamespace(login=1, equity=10000.0, trade_allowed=True, trade_expert=True)

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

    def process_symbol(self, **kwargs):
        self.calls += 1


def test_daily_circuit_breaker_persists_and_blocks(tmp_path):
    breaker = DailyCircuitBreaker(tmp_path / "breaker.json", 0.02)
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert breaker.check(10000.0, now)[0]
    assert breaker.check(9800.0, now)[0]
    ok, reason = breaker.check(9799.0, now)
    assert not ok
    assert "daily drawdown" in reason


def test_runtime_preflight_blocks_unreconciled_journal(tmp_path):
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
    )
    with pytest.raises(RuntimeError, match="unreconciled"):
        runtime.preflight()


def test_runtime_skips_stale_tick(tmp_path):
    now = datetime.now(timezone.utc)
    runtime = LiveRuntime(
        orchestrator=_Orchestrator(), feed=_Feed(now - timedelta(minutes=15)),
        executor=_Executor(now - timedelta(seconds=30)),
        journal=ExecutionJournal(tmp_path / "execution.json"),
        limits=RuntimeLimits(max_tick_age_seconds=10.0),
        clock=lambda: now,
    )
    runtime.preflight = lambda: None
    assert runtime.process_once() == 0
    assert runtime.orchestrator.calls == 0
