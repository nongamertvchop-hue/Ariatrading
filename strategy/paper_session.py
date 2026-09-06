"""Closed-bar orchestration for ARIA paper-trading research.

The runner connects RealtimeMonitor, PaperTradingEngine, and PaperTradeJournal.
It never submits broker orders. A signal observed on bar N becomes eligible
for a paper fill only on bar N+1, preserving the strategy's no-lookahead rule.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from .paper import PaperPosition, PaperTradingEngine
from .journal import PaperTradeJournal, JournalEvent
from .realtime import LiveEvaluation, RealtimeMonitor
from .engine import LONG, SHORT, WAIT


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
        monitor: RealtimeMonitor,
        *,
        paper: PaperTradingEngine | None = None,
        journal: PaperTradeJournal | None = None,
    ) -> None:
        self.monitor = monitor
        self.paper = paper or PaperTradingEngine()
        self.journal = journal or PaperTradeJournal()
        self._pending_signal: LiveEvaluation | None = None

    @property
    def pending_signal(self) -> LiveEvaluation | None:
        return self._pending_signal

    def process_once(self, now: datetime | None = None) -> PaperSessionResult | None:
        """Process the next newly closed candle in deterministic order."""
        evaluation = self.monitor.evaluate_once(now=now)
        if evaluation is None:
            return None

        bar_time = evaluation.bar_time
        signal_event = self.journal.record_signal(
            event_time=evaluation.evaluated_at,
            symbol=evaluation.symbol,
            timeframe=evaluation.timeframe,
            signal=evaluation.signal,
        )

        # Existing positions consume the current closed candle first.
        closed = self.paper.on_bar(evaluation.snapshot.candle.as_dict() | {"time": bar_time}) if self.paper.position else None
        close_event = None
        if closed is not None:
            close_event = self.journal.record_close(
                event_time=closed.exit_time or bar_time,
                symbol=evaluation.symbol,
                timeframe=evaluation.timeframe,
                position=closed,
            )

        # A signal from the immediately preceding evaluation can fill only now.
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
                    entry_price=evaluation.snapshot.current_close,
                )
                if opened is not None:
                    open_event = self.journal.record_open(
                        event_time=opened.entry_time,
                        symbol=pending.symbol,
                        timeframe=pending.timeframe,
                        position=opened,
                    )

        # Only an approved directional signal is eligible for the next bar.
        # WAIT and blocked signals naturally expire after one bar.
        if (
            evaluation.signal.action in {LONG, SHORT}
            and evaluation.supervisor is not None
            and evaluation.supervisor.action == "ALLOW"
            and self.paper.position is None
        ):
            self._pending_signal = evaluation

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
