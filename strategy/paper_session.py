"""Closed-bar orchestration for ARIA paper-trading research.

The runner connects RealtimeMonitor, PaperTradingEngine, and PaperTradeJournal.
It never submits broker orders. A signal observed on bar N becomes eligible
for a paper fill only on bar N+1, preserving the strategy's no-lookahead rule.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .engine import EngineSignal, LONG, SHORT, WAIT
from .journal import JournalEvent, PaperTradeJournal
from .levels_v2 import PriceZone
from .paper import PaperPosition, PaperTradingEngine
from .realtime import LiveEvaluation, RealtimeMonitor


SESSION_STATE_VERSION = 1


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

    def to_state(self) -> dict[str, Any]:
        """Return all mutable session state needed for an exact restart."""
        pending = self._pending_signal
        return {
            "version": SESSION_STATE_VERSION,
            "last_processed_bar_time": self._last_processed_bar_time.isoformat()
            if self._last_processed_bar_time else None,
            "pending_signal": self._pending_state(pending),
            "paper": self.paper.to_state(),
            "journal": self.journal.to_state(),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore a checkpoint and reconcile all cross-component lifecycle state."""
        if not isinstance(state, dict) or state.get("version") != SESSION_STATE_VERSION:
            raise ValueError("unsupported or invalid paper session state version")
        last_raw = state.get("last_processed_bar_time")
        last_bar_time = self._timestamp(last_raw, "last_processed_bar_time") if last_raw else None
        pending = self._pending_from_state(state.get("pending_signal"))
        if pending is not None and last_bar_time is not None and pending.bar_time > last_bar_time:
            raise ValueError("pending signal cannot be newer than last processed bar")
        if pending is not None and pending.signal.action not in {LONG, SHORT}:
            raise ValueError("pending signal must be directional")
        self.paper.restore_state(state.get("paper"))
        self.journal.restore_state(state.get("journal"))

        from live.reconciliation import reconcile_paper_state

        reconcile_paper_state(
            paper=self.paper,
            journal=self.journal,
            pending_signal=pending,
            last_processed_bar_time=last_bar_time,
        )
        self._last_processed_bar_time = last_bar_time
        self._pending_signal = pending

    @staticmethod
    def _pending_state(evaluation: LiveEvaluation | None) -> dict[str, Any] | None:
        if evaluation is None:
            return None
        signal = evaluation.signal
        zone = signal.zone
        return {
            "symbol": evaluation.symbol,
            "timeframe": evaluation.timeframe,
            "bar_time": evaluation.bar_time.isoformat(),
            "signal": {
                "action": signal.action,
                "reason": signal.reason,
                "timeframe": signal.timeframe,
                "protection": signal.protection,
                "breakout_state": signal.breakout_state,
                "entry_reference": signal.entry_reference,
                "stop_reference": signal.stop_reference,
                "test_index": signal.test_index,
                "confirmation_index": signal.confirmation_index,
                "structure_bias": signal.structure_bias,
                "zone": {
                    "low": zone.low,
                    "high": zone.high,
                    "kind": zone.kind,
                    "touches": zone.touches,
                } if zone is not None else None,
            },
        }

    @classmethod
    def _pending_from_state(cls, raw: Any) -> LiveEvaluation | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("pending signal checkpoint is invalid")
        symbol = raw.get("symbol")
        timeframe = raw.get("timeframe")
        if not isinstance(symbol, str) or not symbol or not isinstance(timeframe, str) or not timeframe:
            raise ValueError("pending signal symbol/timeframe is invalid")
        bar_time = cls._timestamp(raw.get("bar_time"), "pending bar_time")
        signal_raw = raw.get("signal")
        if not isinstance(signal_raw, dict):
            raise ValueError("pending signal payload is invalid")
        zone_raw = signal_raw.get("zone")
        zone = None
        if zone_raw is not None:
            if not isinstance(zone_raw, dict):
                raise ValueError("pending signal zone is invalid")
            zone = PriceZone(
                float(zone_raw["low"]),
                float(zone_raw["high"]),
                zone_raw["kind"],
                int(zone_raw["touches"]),
            )
        signal = EngineSignal(
            action=signal_raw.get("action"),
            reason=signal_raw.get("reason"),
            timeframe=signal_raw.get("timeframe"),
            zone=zone,
            protection=signal_raw.get("protection", "SAFE"),
            breakout_state=signal_raw.get("breakout_state", "NO_BREAKOUT"),
            entry_reference=signal_raw.get("entry_reference"),
            stop_reference=signal_raw.get("stop_reference"),
            test_index=signal_raw.get("test_index"),
            confirmation_index=signal_raw.get("confirmation_index"),
            structure_bias=signal_raw.get("structure_bias", "UNKNOWN"),
        )
        if signal.action not in {LONG, SHORT} or signal.timeframe != timeframe:
            raise ValueError("pending signal direction/timeframe is invalid")
        return LiveEvaluation(
            symbol=symbol,
            timeframe=timeframe,
            evaluated_at=bar_time,
            bar_time=bar_time,
            signal=signal,
            support=zone,
            resistance=None,
            snapshot=None,
            supervisor=None,
        )

    @staticmethod
    def _timestamp(value: Any, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be an ISO timestamp")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    def process_once(self, now: datetime | None = None) -> PaperSessionResult | None:
        """Process the next newly closed candle in deterministic order.

        The runner is idempotent at the candle level: a duplicate or old
        evaluation is ignored before it can mutate the paper account or journal.
        Signal journal identity is derived from the closed-bar timestamp, so a
        persistent runtime can deduplicate across process restarts.
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
            signal_time=bar_time,
        )

        had_position_at_bar_start = self.paper.position is not None

        closed = None
        close_event = None
        if had_position_at_bar_start:
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
        if pending is not None and not had_position_at_bar_start and self.paper.position is None:
            signal = pending.signal
            if signal.action in {LONG, SHORT}:
                opened = self.paper.open_from_signal(
                    signal,
                    signal_time=pending.bar_time,
                    entry_time=bar_time,
                    entry_price=evaluation.snapshot.candle.open,
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
