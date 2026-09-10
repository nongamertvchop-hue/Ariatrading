"""Deterministic replay/soak and failure-injection harness for paper runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .paper_runtime_engine import FailureMode, PaperRuntimeEngine, RuntimeBar, RuntimeSignal, RuntimeLifecycle


@dataclass(frozen=True)
class SoakRun:
    bars: int
    events: int
    trades: int
    final_balance: float
    final_equity: float
    max_drawdown: float
    halted: bool
    failures_detected: int
    duplicate_bars_ignored: int


@dataclass(frozen=True)
class ReplayCase:
    name: str
    bars: tuple[RuntimeBar, ...]
    signals: tuple[RuntimeSignal, ...]


@dataclass(frozen=True)
class FailureInjectionResult:
    mode: FailureMode
    halted: bool
    reason: str
    checkpoint_created: bool


def replay(engine: PaperRuntimeEngine, bars: Sequence[RuntimeBar], signals: Sequence[RuntimeSignal] | None = None) -> SoakRun:
    if signals is not None and len(signals) != len(bars):
        raise ValueError("signals and bars must have equal length")
    engine.start()
    duplicate_ignored = 0
    failures = 0
    max_dd = 0.0
    for index, bar in enumerate(bars):
        signal = None if signals is None else signals[index]
        result = engine.process_bar(bar, signal)
        if result.event.event_type == "NO_UPDATE" and "duplicate" in result.reason:
            duplicate_ignored += 1
        if result.lifecycle is RuntimeLifecycle.HALT:
            failures += 1
            break
        max_dd = max(max_dd, engine.account.snapshot().drawdown)
    snapshot = engine.account.snapshot()
    return SoakRun(
        bars=len(bars),
        events=len(engine.events),
        trades=snapshot.trade_count,
        final_balance=snapshot.balance,
        final_equity=snapshot.equity,
        max_drawdown=max_dd,
        halted=engine.lifecycle is RuntimeLifecycle.HALT,
        failures_detected=failures,
        duplicate_bars_ignored=duplicate_ignored,
    )


def inject_failure(engine: PaperRuntimeEngine, mode: FailureMode, *, bar: RuntimeBar, signal: RuntimeSignal) -> FailureInjectionResult:
    engine.set_failure_mode(mode)
    engine.start()
    result = engine.process_bar(bar, signal)
    return FailureInjectionResult(
        mode=FailureMode(mode),
        halted=result.lifecycle is RuntimeLifecycle.HALT,
        reason=result.reason,
        checkpoint_created=engine.checkpoint_path.exists(),
    )


def build_deterministic_dataset(count: int = 10_000, *, start_price: float = 100.0) -> ReplayCase:
    if count < 10:
        raise ValueError("count must be >= 10")
    bars: list[RuntimeBar] = []
    signals: list[RuntimeSignal] = []
    price = float(start_price)
    for index in range(count):
        # Alternating, fully deterministic five-bar waves keep both long and short
        # exits active without random data or look-ahead.
        cycle = index % 6
        delta = (2.0, 3.0, 4.0, -2.0, -3.0, -4.0)[cycle]
        open_price = price
        close = price + delta
        high = max(open_price, close) + 1.0
        low = min(open_price, close) - 1.0
        time = f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}Z"
        bars.append(RuntimeBar(time, open_price, high, low, close))
        if cycle == 0:
            signals.append(RuntimeSignal("LONG", close, close - 5.0, "soak long"))
        elif cycle == 3:
            signals.append(RuntimeSignal("SHORT", close, close + 5.0, "soak short"))
        else:
            signals.append(RuntimeSignal())
        price = close
    return ReplayCase("deterministic-10000", tuple(bars), tuple(signals))


__all__ = ["SoakRun", "ReplayCase", "FailureInjectionResult", "replay", "inject_failure", "build_deterministic_dataset"]
