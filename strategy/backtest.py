"""Signal-only historical backtest for the two basic price-action setups.

This module evaluates completed candles sequentially and never uses future
candles to create a signal. It records LONG/SHORT/WAIT decisions and basic
signal statistics. It does not connect to a broker or place orders.

This is for educational research only, not financial advice.
"""

from dataclasses import dataclass

from .engine import LONG, SHORT, WAIT, EngineSignal, evaluate_long, evaluate_short
from .levels_v2 import PriceZone, find_resistance_zones, find_support_zones
from .timeframe import get_timeframe_config


@dataclass(frozen=True)
class BacktestResult:
    timeframe: str
    candles_tested: int
    long_signals: int
    short_signals: int
    wait_signals: int
    signals: tuple[EngineSignal, ...]

    @property
    def total_directional_signals(self) -> int:
        return self.long_signals + self.short_signals

    @property
    def signal_rate(self) -> float:
        if self.candles_tested == 0:
            return 0.0
        return self.total_directional_signals / self.candles_tested


def _latest_zones(history: list[dict]) -> tuple[list[PriceZone], list[PriceZone]]:
    """Build zones only from candles already closed in the test timeline."""
    supports = find_support_zones(history)
    resistances = find_resistance_zones(history)
    return supports, resistances


def _nearest_support(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    candidates = [z for z in zones if float(candle["low"]) <= z.high]
    return min(candidates, key=lambda z: abs(z.center - float(candle["close"])), default=None)


def _nearest_resistance(candle: dict, zones: list[PriceZone]) -> PriceZone | None:
    candidates = [z for z in zones if float(candle["high"]) >= z.low]
    return min(candidates, key=lambda z: abs(z.center - float(candle["close"])), default=None)


def run_backtest(
    candles: list[dict],
    timeframe: str,
    warmup: int | None = None,
) -> BacktestResult:
    """Run a signal-only sequential test over OHLC candles.

    A signal is evaluated using history ending at the current completed candle.
    The first `warmup` candles are excluded so the zone detector has history.
    """
    config = get_timeframe_config(timeframe)
    if not candles:
        return BacktestResult(timeframe, 0, 0, 0, 0, ())

    minimum_warmup = max(config.lookback + 2, 10)
    start = minimum_warmup if warmup is None else max(warmup, minimum_warmup)
    start = min(start, len(candles))

    signals: list[EngineSignal] = []
    for i in range(start, len(candles)):
        history = candles[: i + 1]
        current = candles[i]
        supports, resistances = _latest_zones(history)

        support = _nearest_support(current, supports)
        resistance = _nearest_resistance(current, resistances)

        candidates: list[EngineSignal] = []
        if support is not None:
            candidates.append(evaluate_long(history, support, timeframe))
        if resistance is not None:
            candidates.append(evaluate_short(history, resistance, timeframe))

        directional = [s for s in candidates if s.action in {LONG, SHORT}]
        if len(directional) == 1:
            signals.append(directional[0])
        else:
            signals.append(
                EngineSignal(
                    WAIT,
                    "no unique directional setup",
                    timeframe,
                )
            )

    longs = sum(s.action == LONG for s in signals)
    shorts = sum(s.action == SHORT for s in signals)
    waits = sum(s.action == WAIT for s in signals)
    return BacktestResult(
        timeframe=timeframe,
        candles_tested=len(signals),
        long_signals=longs,
        short_signals=shorts,
        wait_signals=waits,
        signals=tuple(signals),
    )


def run_all_timeframes(candles_by_timeframe: dict[str, list[dict]]) -> dict[str, BacktestResult]:
    """Run the same strategy independently on every supported timeframe."""
    results: dict[str, BacktestResult] = {}
    for timeframe, candles in candles_by_timeframe.items():
        results[timeframe] = run_backtest(candles, timeframe)
    return results
