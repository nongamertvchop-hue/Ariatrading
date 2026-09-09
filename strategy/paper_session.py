"""Closed-bar orchestration for ARIA paper-trading research.

The runner connects RealtimeMonitor, PaperTradingEngine, and PaperTradeJournal.
It never submits broker orders. A signal observed on bar N becomes eligible
for a paper fill only on bar N+1, preserving the strategy's no-lookahead rule.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .engine import LONG, SHORT
from .journal import JournalEvent, PaperTradeJournal
from .paper import PaperPosition, PaperTradingEngine
from .realtime import LiveEvaluation, RealtimeMonitor


class _MonitorLike(Protocol):
    def evaluate_once(self, now: datetime | None = None) -> LiveEvaluation | None:
        """Return the next newly closed-bar evaluation."""


@dataclass(frozen=True)
class PaperSessionResult:
    evaluation: LiveEvaluation
    opened: PaperPosition | None
    closed: PaperPosition | None
    signal_event: JournalEvent
    open_event: JournalEvent | None
    close_event: JournalEvent | None


class PaperSessionRunner:
    """Drive one paper session from newly closed realtime candles."""

    def __init__(
        self,
        monitor: RealtimeMonitor | _MonitorLike,
        *,
        paper: PaperTradingEngine | None = None,
        journal: PaperTradeJournal | None = None,
    ) -> None:
        self.monitor = monitor
        self.paper = paper or PaperTradingEngine()
        self.journal = journal or PaperTradeJournal()
        self._pending_signal: LiveEvaluation | None = None
        self._last_processed_bar_time: datetime | None = None

    @property
    def pending_signal(self) -> LiveEvaluation | None:
        return self._pending_signal

    @property
    def last_processed_bar_time(self) -> datetime | None:
        """Timestamp of the most recently processed closed candle."""
        return self._last_processed_bar_time

    def process_once(self, now: datetime | None = None) -> PaperSessionResult | None:
        """Process the next newly closed candle in deterministic order.

        The runner is idempotent at the candle level: a duplicate or old
        evaluation is ignored before it can mutate the paper account or journal.
        """
        evaluation = self.monitor.evaluate_once(now=now)
        if evaluation is None:
            return None
        if evaluation.snapshot is None:
            raise RuntimeError("realtime evaluation must include a market snapshot")
        if self._last_processed_bar_time is not None and evaluation.bar_time <= self._last_processed_bar_time:
            return None

        bar_time = evaluation.bar_time
        signal_event = self.journal.record_signal(
            event_time=evaluation.evaluated_at,
            symbol=evaluation.symbol,
            timeframe=evaluation.timeframe,
            signal=evaluation.signal,
            event_id=evaluation.event_id,
        )

        closed = None
        close_event = None
        if self.paper.position is not None:
            bar = {
                "time": bar_time,
                "open": evaluation.snapshot.candle.open,
                "high": evaluation.snapshot.candle.high,
                "low": evaluation.snapshot.candle.low,
                "close": evaluation.snapshot.candle.close,
            }
            closed = self.paper.on_bar(bar)
            if closed is not None:
                close_event = self.journal.record_close(
                    event_time=closed.exit_time or bar_time,
                    symbol=evaluation.symbol,
                    timeframe=evaluation.timeframe,
                    position=closed,
                )

        opened = None
        open_event = None
        pending = self._pending_signal
        self._pending_signal = None
        if pending is not None and self.paper.position is None:
            signal = pending.signal
            if signal.action in {LONG, SHORT}:
                opened = self.paper.open_from_signal(
                    signal,
                    signal_time=pending.bar_time,
                    entry_time=bar_time,
                    entry_price=evaluation.snapshot.candle.open,
                    signal_event_id=pending.event_id,
                )
                if opened is not None:
                    open_event = self.journal.record_open(
                        event_time=opened.entry_time,
                        symbol=pending.symbol,
                        timeframe=pending.timeframe,
                        position=opened,
                    )

        if (
            evaluation.signal.action in {LONG, SHORT}
            and evaluation.supervisor is not None
            and evaluation.supervisor.action == "ALLOW"
            and self.paper.position is None
        ):
            self._pending_signal = evaluation

        self._last_processed_bar_time = bar_time
        return PaperSessionResult(
            evaluation=evaluation,
            opened=opened,
            closed=closed,
            signal_event=signal_event,
            open_event=open_event,
            close_event=close_event,
        )

    def run(self, steps: int, now: datetime | None = None) -> list[PaperSessionResult]:
        """Process up to ``steps`` newly closed candles."""
        if steps < 1:
            raise ValueError("steps must be >= 1")
        results: list[PaperSessionResult] = []
        for _ in range(steps):
            result = self.process_once(now=now)
            if result is None:
                break
            results.append(result)
        return results
