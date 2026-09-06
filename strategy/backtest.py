"""Sequential historical research pipeline for Ariatrading."""

from dataclasses import dataclass
from datetime import datetime

from .engine import LONG, SHORT, WAIT, EngineSignal, evaluate_long, evaluate_short
from .execution import ExecutionModel, simulate_realistic_exit
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .mtf import bar_duration, build_timestamp_aligned_mtf_context
from .risk import LOSS, OPEN, WIN, RiskPlan, TradeResult, build_risk_plan, simulate_exit
from .timeframe import adaptive_confirmation_buffer, adaptive_zone_tolerance, get_timeframe_config
from .validation import ResearchMetrics, evaluate_trades


@dataclass(frozen=True)
class BacktestResult:
    timeframe: str
    candles_tested: int
    long_signals: int
    short_signals: int
    wait_signals: int
    trades: tuple[TradeResult, ...]
    signals: tuple[EngineSignal, ...]

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
    candidates = [z for z in zones if float(candle["low"]) <= z.high]
    return min(candidates, key=lambda z: abs(z.center - float(candle["close"])), default=None)


def _nearest_resistance(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    candidates = [z for z in zones if float(candle["high"]) >= z.low]
    return min(candidates, key=lambda z: abs(z.center - float(candle["close"])), default=None)


def _mtf_for_current(candles_by_timeframe, timeframe: str, current: dict):
    if candles_by_timeframe is None:
        return None
    timestamp = current.get("time")
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("MTF backtest requires timezone-aware datetime candle times")
    return build_timestamp_aligned_mtf_context(candles_by_timeframe, timeframe, timestamp + bar_duration(timeframe))


def run_backtest(candles: list[dict], timeframe: str, warmup: int | None = None, reward_risk: float = 2.0,
                 max_hold_bars: int = 20, mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
                 execution_model: ExecutionModel | None = None) -> BacktestResult:
    """Run strategy -> risk -> optional execution-cost simulation sequentially."""
    config = get_timeframe_config(timeframe)
    if reward_risk <= 0 or max_hold_bars < 1:
        raise ValueError("reward_risk must be > 0 and max_hold_bars must be >= 1")
    if not candles:
        return BacktestResult(timeframe, 0, 0, 0, 0, (), ())

    start = min(max(config.lookback + 2, 10, warmup or 0), len(candles))
    signals, trades = [], []
    i = start
    while i < len(candles):
        current, prior = candles[i], candles[:i]
        supports, resistances = _latest_zones(prior, timeframe)
        mtf = _mtf_for_current(mtf_candles_by_timeframe, timeframe, current)
        candidates = []
        support = _nearest_support(current, supports)
        resistance = _nearest_resistance(current, resistances)
        if support:
            candidates.append(evaluate_long(candles[:i + 1], support, timeframe, mtf=mtf))
        if resistance:
            candidates.append(evaluate_short(candles[:i + 1], resistance, timeframe, mtf=mtf))

        directional = [s for s in candidates if s.action in {LONG, SHORT}]
        if len(directional) == 1:
            signal = directional[0]
        elif len(directional) == 2 and all(s.score is not None for s in directional) and directional[0].score.total != directional[1].score.total:
            signal = max(directional, key=lambda s: s.score.total)
        else:
            signal = EngineSignal(WAIT, "no unique directional setup", timeframe)
        signals.append(signal)

        if signal.action in {LONG, SHORT} and signal.entry_reference is not None and signal.zone is not None:
            plan: RiskPlan = build_risk_plan(signal.action, signal.entry_reference, signal.zone,
                                             adaptive_confirmation_buffer(prior, timeframe), reward_risk)
            future = candles[i + 1:i + 1 + max_hold_bars]
            trade = simulate_exit(plan, future, max_hold_bars) if execution_model is None else simulate_realistic_exit(plan, future, execution_model, max_hold_bars)
            trades.append(trade)
            if trade.bars_held > 0:
                i += trade.bars_held + 1
                continue
        i += 1

    return BacktestResult(timeframe, len(signals), sum(s.action == LONG for s in signals),
                          sum(s.action == SHORT for s in signals), sum(s.action == WAIT for s in signals),
                          tuple(trades), tuple(signals))


def run_all_timeframes(candles_by_timeframe: dict[str, list[dict]], reward_risk: float = 2.0,
                       max_hold_bars: int = 20, execution_model: ExecutionModel | None = None):
    return {tf: run_backtest(c, tf, reward_risk=reward_risk, max_hold_bars=max_hold_bars,
                             execution_model=execution_model) for tf, c in candles_by_timeframe.items()}
