"""Sequential historical research pipeline for Ariatrading."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from .engine import LONG, SHORT, WAIT, EngineSignal, evaluate_long, evaluate_short
from .execution import ExecutionModel, entry_price, simulate_realistic_exit
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .mtf import bar_duration, build_timestamp_aligned_mtf_context
from .risk import LOSS, OPEN, WIN, RiskPlan, TradeResult, build_risk_plan, simulate_exit
from .timeframe import adaptive_confirmation_buffer, adaptive_zone_tolerance, get_timeframe_config
from .validation import ResearchMetrics, evaluate_trades


ENTRY_TIMING_SIGNAL_REFERENCE = "signal_reference"
ENTRY_TIMING_NEXT_BAR_OPEN = "next_bar_open"
SignalFilter = Callable[[int, EngineSignal], bool]


@dataclass(frozen=True)
class BacktestResult:
    timeframe: str
    candles_tested: int
    long_signals: int
    short_signals: int
    wait_signals: int
    trades: tuple[TradeResult, ...]
    signals: tuple[EngineSignal, ...]
    signal_indices: tuple[int, ...] = ()

    @property
    def total_directional_signals(self) -> int:
        return self.long_signals + self.short_signals

    @property
    def signal_rate(self) -> float:
        return self.total_directional_signals / self.candles_tested if self.candles_tested else 0.0

    @property
    def wins(self) -> int:
        return sum(t.outcome == WIN for t in self.trades)

    @property
    def losses(self) -> int:
        return sum(t.outcome == LOSS for t in self.trades)

    @property
    def open_trades(self) -> int:
        return sum(t.outcome == OPEN for t in self.trades)

    @property
    def closed_trades(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return self.wins / self.closed_trades if self.closed_trades else 0.0

    @property
    def net_r(self) -> float:
        return sum(t.r_multiple for t in self.trades)

    @property
    def expectancy_r(self) -> float:
        return self.net_r / self.closed_trades if self.closed_trades else 0.0

    def research_metrics(self) -> ResearchMetrics:
        return evaluate_trades(self.trades)


def _latest_zones(history: list[dict], timeframe: str):
    tolerance = adaptive_zone_tolerance(history, timeframe)
    return find_support_zones(history, tolerance=tolerance), find_resistance_zones(history, tolerance=tolerance)


def _nearest_support(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    price = float(candle["close"])
    candidates = [z for z in zones if z.center <= price]
    return min(candidates, key=lambda z: price - z.center, default=None)


def _nearest_resistance(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    price = float(candle["close"])
    candidates = [z for z in zones if z.center >= price]
    return min(candidates, key=lambda z: z.center - price, default=None)


def _best_signal(signals: Sequence[EngineSignal]) -> EngineSignal:
    directional = [signal for signal in signals if signal.action != WAIT]
    if not directional:
        return signals[0] if signals else EngineSignal(WAIT, "no setup", "")
    return max(directional, key=lambda signal: signal.score.total if signal.score is not None else -1)


def _select_signal(long_signal: EngineSignal, short_signal: EngineSignal) -> EngineSignal:
    if long_signal.action != WAIT and short_signal.action == WAIT:
        return long_signal
    if short_signal.action != WAIT and long_signal.action == WAIT:
        return short_signal
    if long_signal.action == WAIT and short_signal.action == WAIT:
        return EngineSignal(WAIT, "no directional setup", long_signal.timeframe)
    long_score = long_signal.score.total if long_signal.score is not None else -1
    short_score = short_signal.score.total if short_signal.score is not None else -1
    return long_signal if long_score > short_score else short_signal


def _mtf_for_current(candles_by_timeframe, timeframe: str, current: dict):
    if candles_by_timeframe is None:
        return None
    timestamp = current.get("time")
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("MTF backtest requires timezone-aware datetime candle times")
    return build_timestamp_aligned_mtf_context(candles_by_timeframe, timeframe, timestamp + bar_duration(timeframe))


def run_backtest(
    candles: list[dict],
    timeframe: str,
    warmup: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
    execution_model: ExecutionModel | None = None,
    start_index: int | None = None,
    end_index: int | None = None,
    entry_timing: str = ENTRY_TIMING_SIGNAL_REFERENCE,
    signal_filter: SignalFilter | None = None,
) -> BacktestResult:
    """Run strategy/risk sequentially over a bounded research window.

    Signal selection intentionally mirrors the realtime research path: all
    support and resistance candidates are evaluated, the highest-scoring
    directional candidate is selected, and nearest zones are used only for
    context calculations. This keeps backtest/replay signal semantics aligned.
    """
    config = get_timeframe_config(timeframe)
    if reward_risk <= 0 or max_hold_bars < 1:
        raise ValueError("reward_risk must be > 0 and max_hold_bars must be >= 1")
    if entry_timing not in {ENTRY_TIMING_SIGNAL_REFERENCE, ENTRY_TIMING_NEXT_BAR_OPEN}:
        raise ValueError("entry_timing must be 'signal_reference' or 'next_bar_open'")
    if not candles:
        return BacktestResult(timeframe, 0, 0, 0, 0, (), (), ())

    if start_index is None:
        start_index = 0
    if end_index is None:
        end_index = len(candles)
    if not 0 <= start_index < len(candles):
        raise ValueError("start_index must be within candles")
    if not start_index < end_index <= len(candles):
        raise ValueError("end_index must be > start_index and <= len(candles)")

    normal_warm_start = min(max(config.lookback + 2, 10, warmup or 0), len(candles))
    evaluation_start = normal_warm_start if start_index == 0 else start_index
    if evaluation_start >= end_index:
        return BacktestResult(timeframe, 0, 0, 0, 0, (), (), ())

    signals, signal_indices, trades = [], [], []
    i = evaluation_start
    while i < end_index:
        current, prior = candles[i], candles[:i]
        supports, resistances = _latest_zones(prior, timeframe)
        mtf = _mtf_for_current(mtf_candles_by_timeframe, timeframe, current)
        long_candidates = [evaluate_long(candles[:i + 1], zone, timeframe, mtf=mtf) for zone in supports]
        short_candidates = [evaluate_short(candles[:i + 1], zone, timeframe, mtf=mtf) for zone in resistances]
        long_signal = _best_signal(long_candidates) if long_candidates else EngineSignal(WAIT, "no support zone", timeframe)
        short_signal = _best_signal(short_candidates) if short_candidates else EngineSignal(WAIT, "no resistance zone", timeframe)
        signal = _select_signal(long_signal, short_signal)
        signals.append(signal)
        signal_indices.append(i)

        if (
            signal.action in {LONG, SHORT}
            and signal.entry_reference is not None
            and signal.zone is not None
            and (signal_filter is None or signal_filter(i, signal))
        ):
            if entry_timing == ENTRY_TIMING_NEXT_BAR_OPEN:
                fill_index = i + 1
                if fill_index >= end_index:
                    i += 1
                    continue
                reference_entry = float(candles[fill_index]["open"])
                future_start = fill_index + 1
            else:
                reference_entry = float(signal.entry_reference)
                future_start = i + 1

            if execution_model is None:
                entry = reference_entry
                plan = build_risk_plan(signal.action, entry, signal.zone, adaptive_confirmation_buffer(prior, timeframe), reward_risk)
                future = candles[future_start:min(end_index, future_start + max_hold_bars)]
                trade = simulate_exit(plan, future, max_hold_bars)
            else:
                entry = entry_price(reference_entry, signal.action, execution_model)
                plan: RiskPlan = build_risk_plan(signal.action, entry, signal.zone, adaptive_confirmation_buffer(prior, timeframe), reward_risk)
                future = candles[future_start:min(end_index, future_start + max_hold_bars)]
                trade = simulate_realistic_exit(plan, future, execution_model, max_hold_bars, entry_is_effective=True)

            trades.append(trade)
            if trade.bars_held > 0 and trade.outcome in {WIN, LOSS}:
                i = future_start + trade.bars_held
                continue
        i += 1

    return BacktestResult(
        timeframe,
        len(signals),
        sum(s.action == LONG for s in signals),
        sum(s.action == SHORT for s in signals),
        sum(s.action == WAIT for s in signals),
        tuple(trades),
        tuple(signals),
        tuple(signal_indices),
    )


def run_all_timeframes(
    candles_by_timeframe: dict[str, list[dict]],
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    execution_model: ExecutionModel | None = None,
    entry_timing: str = ENTRY_TIMING_SIGNAL_REFERENCE,
):
    return {
        tf: run_backtest(c, tf, reward_risk=reward_risk, max_hold_bars=max_hold_bars, execution_model=execution_model, entry_timing=entry_timing)
        for tf, c in candles_by_timeframe.items()
    }


__all__ = ["BacktestResult", "ENTRY_TIMING_NEXT_BAR_OPEN", "ENTRY_TIMING_SIGNAL_REFERENCE", "SignalFilter", "run_all_timeframes", "run_backtest"]
