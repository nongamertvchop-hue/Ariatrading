from pathlib import Path

import pytest

from strategy.paper_accounting import LONG, SHORT, PaperAccounting
from strategy.paper_runtime_engine import FailureMode, PaperRuntimeEngine, RuntimeBar, RuntimeLifecycle, RuntimeSignal
from strategy.paper_soak import build_deterministic_dataset, inject_failure, replay


def bar(ts: str, price: float, high: float | None = None, low: float | None = None) -> RuntimeBar:
    return RuntimeBar(ts, price, high if high is not None else price + 0.5, low if low is not None else price - 0.5, price)


def test_accounting_realized_unrealized_equity_and_drawdown():
    account = PaperAccounting(initial_balance=10_000, fee_per_unit=0.5)
    account.open_position(symbol="EURUSD", side=LONG, quantity=10, entry_price=100, bar_time="1")
    marked = account.mark(price=98, bar_time="2")
    assert marked.unrealized_pnl == -20
    assert marked.equity == 9_980
    assert marked.drawdown == 20
    trade = account.close_position(exit_price=105, bar_time="3")
    assert trade.gross_pnl == 50
    assert trade.fees == 5
    assert trade.net_pnl == 45
    final = account.snapshot()
    assert final.balance == 10_045
    assert final.realized_pnl == 45
    assert final.trade_count == 1
    assert final.win_count == 1


def test_short_accounting_is_signed_correctly():
    account = PaperAccounting(initial_balance=1_000)
    account.open_position(symbol="EURUSD", side=SHORT, quantity=2, entry_price=100, bar_time="1")
    assert account.snapshot(mark_price=95).unrealized_pnl == 10
    trade = account.close_position(exit_price=90, bar_time="2")
    assert trade.net_pnl == 20


def test_runtime_opens_and_closes_on_completed_bars(tmp_path: Path):
    engine = PaperRuntimeEngine(checkpoint_path=tmp_path / "runtime.json")
    assert engine.start().accepted
    opened = engine.process_bar(
        bar("1", 100), RuntimeSignal("LONG", 100, 95, "support reclaim")
    )
    assert opened.lifecycle is RuntimeLifecycle.OPEN
    closed = engine.process_bar(bar("2", 110, high=111, low=99), RuntimeSignal())
    assert closed.event.event_type in {"CLOSED", "NO_UPDATE"}
    # Target is 110 and the bar reaches it, so the account must be flat.
    assert engine.account.position is None
    assert engine.account.snapshot().trade_count == 1


def test_duplicate_and_out_of_order_bars_fail_safely(tmp_path: Path):
    engine = PaperRuntimeEngine(checkpoint_path=tmp_path / "runtime.json")
    engine.start()
    engine.process_bar(bar("2", 100), RuntimeSignal())
    duplicate = engine.process_bar(bar("2", 101), RuntimeSignal())
    assert duplicate.reason == "duplicate completed bar ignored"
    old = engine.process_bar(bar("1", 99), RuntimeSignal())
    assert old.lifecycle is RuntimeLifecycle.HALT
    assert "out-of-order" in old.reason


def test_restart_recovery_restores_equity_and_last_bar(tmp_path: Path):
    checkpoint = tmp_path / "runtime.json"
    first = PaperRuntimeEngine(checkpoint_path=checkpoint)
    first.start()
    first.process_bar(bar("1", 100), RuntimeSignal("LONG", 100, 95, "entry"))
    first.process_bar(bar("2", 103), RuntimeSignal())

    second = PaperRuntimeEngine(checkpoint_path=checkpoint)
    recovered = second.recover()
    assert recovered.accepted
    assert second.lifecycle is RuntimeLifecycle.OPEN
    assert second.last_processed_bar_time == "2"
    assert second.account.position is not None
    assert second.account.snapshot().equity > 10_000


def test_pending_execution_never_promotes_to_filled_after_restart(tmp_path: Path):
    checkpoint = tmp_path / "runtime.json"
    first = PaperRuntimeEngine(checkpoint_path=checkpoint)
    first.set_failure_mode(FailureMode.TIMEOUT_AFTER_ACCEPT)
    first.start()
    result = first.process_bar(bar("1", 100), RuntimeSignal("LONG", 100, 95, "entry"))
    assert result.lifecycle is RuntimeLifecycle.HALT

    second = PaperRuntimeEngine(checkpoint_path=checkpoint)
    recovered = second.recover()
    assert recovered.lifecycle is RuntimeLifecycle.HALT
    assert "pending paper order" in recovered.reason
    assert second.account.position is None


def test_corrupt_checkpoint_fails_closed_without_overwriting_it(tmp_path: Path):
    checkpoint = tmp_path / "runtime.json"
    checkpoint.write_text("not-json", encoding="utf-8")
    engine = PaperRuntimeEngine(checkpoint_path=checkpoint)
    result = engine.recover()
    assert result.lifecycle is RuntimeLifecycle.HALT
    assert "checkpoint recovery failed" in result.reason
    assert checkpoint.read_text(encoding="utf-8") == "not-json"


@pytest.mark.parametrize(
    "mode",
    [FailureMode.DISCONNECT_BEFORE_SUBMIT, FailureMode.TIMEOUT_AFTER_ACCEPT, FailureMode.PARTIAL_FILL],
)
def test_final_failure_injection_modes_halt(tmp_path: Path, mode: FailureMode):
    engine = PaperRuntimeEngine(checkpoint_path=tmp_path / f"{mode.value}.json")
    result = inject_failure(engine, mode, bar=bar("1", 100), signal=RuntimeSignal("LONG", 100, 95, "entry"))
    assert result.halted
    assert result.checkpoint_created


def test_rejection_does_not_open_position(tmp_path: Path):
    engine = PaperRuntimeEngine(checkpoint_path=tmp_path / "reject.json")
    result = inject_failure(engine, FailureMode.REJECT, bar=bar("1", 100), signal=RuntimeSignal("LONG", 100, 95, "entry"))
    assert not result.halted
    assert engine.account.position is None
    assert engine.account.snapshot().trade_count == 0


def test_massive_deterministic_soak_is_replayable(tmp_path: Path):
    case = build_deterministic_dataset(10_000)
    first = replay(PaperRuntimeEngine(checkpoint_path=tmp_path / "a.json"), case.bars, case.signals)
    second = replay(PaperRuntimeEngine(checkpoint_path=tmp_path / "b.json"), case.bars, case.signals)
    assert first.bars == second.bars == 10_000
    assert first.halted is False
    assert first.trades == second.trades
    assert first.final_balance == second.final_balance
    assert first.final_equity == second.final_equity
    assert first.max_drawdown == second.max_drawdown
