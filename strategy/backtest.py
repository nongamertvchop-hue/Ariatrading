"""Historical backtest for the two basic price-action setups.

Pipeline:
    confirmed zones -> multi-candle signal -> hypothetical SL/TP -> exit stats.

The test is sequential and uses only information available before each signal
candle. It is educational research code: no broker connection or order
execution is performed.
"""

from dataclasses import dataclass
from datetime import datetime

from .engine import LONG, SHORT, WAIT, EngineSignal, evaluate_long, evaluate_short
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .mtf import bar_duration, build_timestamp_aligned_mtf_context
from .risk import LOSS, OPEN, WIN, RiskPlan, TradeResult, build_risk_plan, simulate_exit
from .timeframe import adaptive_confirmation_buffer, adaptive_zone_tolerance, get_timeframe_config


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


def _latest_zones(history: list[dict], timeframe: str) -> tuple[list[PriceZone], list[PriceZone]]:
    """Build zones from already-closed candles, excluding the current candle."""
    tolerance = adaptive_zone_tolerance(history, timeframe)
    supports = find_support_zones(history, tolerance=tolerance)
    resistances = find_resistance_zones(history, tolerance=tolerance)
    return supports, resistances


def _nearest_support(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    price = float(candle["close"])
    candidates = [z for z in zones if float(candle["low"]) <= z.high]
    return min(candidates, key=lambda z: abs(z.center - price), default=None)


def _nearest_resistance(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    price = float(candle["close"])
    candidates = [z for z in zones if float(candle["high"]) >= z.low]
    return min(candidates, key=lambda z: abs(z.center - price), default=None)


def _empty_result(timeframe: str) -> BacktestResult:
    return BacktestResult(timeframe, 0, 0, 0, 0, (), ())


def _mtf_for_current(
    candles_by_timeframe: dict[str, list[dict]] | None,
    timeframe: str,
    current: dict,
) -> object | None:
    """Build timestamp-aligned MTF context for a closed historical candle."""
    if candles_by_timeframe is None:
        return None
    timestamp = current.get("time")
    if not isinstance(timestamp, datetime):
        raise ValueError("MTF backtest requires timezone-aware datetime candle times")
    if timestamp.tzinfo is None:
        raise ValueError("MTF backtest requires timezone-aware datetime candle times")
    entry_timestamp = timestamp + bar_duration(timeframe)
    return build_timestamp_aligned_mtf_context(
        candles_by_timeframe,
        timeframe,
        entry_timestamp,
    )


def run_backtest(
    candles: list[dict],
    timeframe: str,
    warmup: int | None = None,
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
    mtf_candles_by_timeframe: dict[str, list[dict]] | None = None,
) -> BacktestResult:
    """Run a sequential signal + SL/TP backtest.

    Entry is the signal candle close. Stop is placed beyond the reaction zone
    by an adaptive distance. Target is `reward_risk` times the initial risk.
    One hypothetical position is allowed at a time. If both stop and target are
    touched in one candle, the conservative simulator counts the stop first.

    If timestamped multi-timeframe candles are supplied, MTF context is aligned
    to each signal candle close and only fully closed higher-timeframe candles
    are used. Without timestamps, MTF integration is intentionally unavailable
    rather than guessing and risking look-ahead bias.
    """
    config = get_timeframe_config(timeframe)
    if reward_risk <= 0:
        raise ValueError("reward_risk must be > 0")
    if max_hold_bars < 1:
        raise ValueError("max_hold_bars must be >= 1")
    if not candles:
        return _empty_result(timeframe)

    minimum_warmup = max(config.lookback + 2, 10)
    start = minimum_warmup if warmup is None else max(warmup, minimum_warmup)
    start = min(start, len(candles))

    signals: list[EngineSignal] = []
    trades: list[TradeResult] = []
    i = start

    while i < len(candles):
        current = candles[i]
        prior = candles[:i]
        supports, resistances = _latest_zones(prior, timeframe)
        support = _nearest_support(current, supports)
        resistance = _nearest_resistance(current, resistances)
        mtf = _mtf_for_current(mtf_candles_by_timeframe, timeframe, current)

        candidates: list[EngineSignal] = []
        if support is not None:
            candidates.append(evaluate_long(candles[: i + 1], support, timeframe, mtf=mtf))
        if resistance is not None:
            candidates.append(evaluate_short(candles[: i + 1], resistance, timeframe, mtf=mtf))

        directional = [s for s in candidates if s.action in {LONG, SHORT}]
        if len(directional) == 1:
            signal = directional[0]
        elif len(directional) > 1:
            scored = [s for s in directional if s.score is not None]
            if len(scored) == 2 and scored[0].score.total != scored[1].score.total:
                signal = max(scored, key=lambda s: s.score.total)
            else:
                signal = EngineSignal(WAIT, "no unique directional setup", timeframe)
        else:
            signal = EngineSignal(WAIT, "no unique directional setup", timeframe)
        signals.append(signal)

        if signal.action in {LONG, SHORT} and signal.entry_reference is not None and signal.zone is not None:
            buffer = adaptive_confirmation_buffer(prior, timeframe)
            plan: RiskPlan = build_risk_plan(
                signal.action,
                signal.entry_reference,
                signal.zone,
                stop_buffer=buffer,
                reward_risk=reward_risk,
            )
            future = candles[i + 1 : i + 1 + max_hold_bars]
            trade = simulate_exit(plan, future, max_hold_bars)
            trades.append(trade)
            if trade.bars_held > 0:
                i += trade.bars_held + 1
                continue

        i += 1

    longs = sum(s.action == LONG for s in signals)
    shorts = sum(s.action == SHORT for s in signals)
    waits = sum(s.action == WAIT for s in signals)
    return BacktestResult(timeframe, len(signals), longs, shorts, waits, tuple(trades), tuple(signals))


def run_all_timeframes(
    candles_by_timeframe: dict[str, list[dict]],
    reward_risk: float = 2.0,
    max_hold_bars: int = 20,
) -> dict[str, BacktestResult]:
    """Run the same strategy independently on every supported timeframe."""
    return {
        timeframe: run_backtest(candles, timeframe, reward_risk=reward_risk, max_hold_bars=max_hold_bars)
        for timeframe, candles in candles_by_timeframe.items()
    }
