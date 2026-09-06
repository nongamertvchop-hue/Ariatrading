"""Educational risk and exit simulation for historical research.

No broker connection and no order execution. The functions only calculate
hypothetical stop/target levels and simulate exits on historical candles.
"""

from dataclasses import dataclass

from .levels_v2 import PriceZone, SUPPORT, RESISTANCE

LONG = "LONG"
SHORT = "SHORT"
WIN = "WIN"
LOSS = "LOSS"
OPEN = "OPEN"


@dataclass(frozen=True)
class RiskPlan:
    direction: str
    entry: float
    stop: float
    target: float
    risk_distance: float
    reward_distance: float
    rr: float


@dataclass(frozen=True)
class TradeResult:
    direction: str
    entry: float
    stop: float
    target: float
    exit_price: float | None
    outcome: str
    bars_held: int
    r_multiple: float


def build_risk_plan(
    direction: str,
    entry: float,
    zone: PriceZone,
    stop_buffer: float,
    reward_risk: float = 2.0,
) -> RiskPlan:
    if direction not in {LONG, SHORT}:
        raise ValueError("direction must be LONG or SHORT")
    if reward_risk <= 0:
        raise ValueError("reward_risk must be > 0")
    if stop_buffer < 0:
        raise ValueError("stop_buffer must be >= 0")

    if direction == LONG:
        if zone.kind != SUPPORT:
            raise ValueError("LONG requires SUPPORT")
        stop = zone.low - stop_buffer
        risk = entry - stop
        target = entry + risk * reward_risk
    else:
        if zone.kind != RESISTANCE:
            raise ValueError("SHORT requires RESISTANCE")
        stop = zone.high + stop_buffer
        risk = stop - entry
        target = entry - risk * reward_risk

    if risk <= 0:
        raise ValueError("entry must be beyond the stop in the trade direction")
    return RiskPlan(direction, entry, stop, target, risk, abs(target - entry), reward_risk)


def simulate_exit(plan: RiskPlan, future_candles: list[dict], max_bars: int | None = None) -> TradeResult:
    """Simulate the first stop/target hit after entry.

    If both stop and target are touched inside one OHLC candle, STOP is assumed
    first because intrabar order is unknown. This conservative assumption avoids
    overstating historical performance.
    """
    if max_bars is not None and max_bars < 1:
        raise ValueError("max_bars must be >= 1")
    sample = future_candles if max_bars is None else future_candles[:max_bars]

    for i, raw in enumerate(sample, start=1):
        high = float(raw["high"])
        low = float(raw["low"])
        if high < low:
            raise ValueError("candle high must be >= low")

        if plan.direction == LONG:
            hit_stop = low <= plan.stop
            hit_target = high >= plan.target
            if hit_stop:
                return TradeResult(LONG, plan.entry, plan.stop, plan.target, plan.stop, LOSS, i, -1.0)
            if hit_target:
                return TradeResult(LONG, plan.entry, plan.stop, plan.target, plan.target, WIN, i, plan.rr)
        else:
            hit_stop = high >= plan.stop
            hit_target = low <= plan.target
            if hit_stop:
                return TradeResult(SHORT, plan.entry, plan.stop, plan.target, plan.stop, LOSS, i, -1.0)
            if hit_target:
                return TradeResult(SHORT, plan.entry, plan.stop, plan.target, plan.target, WIN, i, plan.rr)

    return TradeResult(plan.direction, plan.entry, plan.stop, plan.target, None, OPEN, len(sample), 0.0)
