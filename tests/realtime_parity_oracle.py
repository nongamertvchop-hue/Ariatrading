"""Emit deterministic Python realtime decisions for cross-runtime parity tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from strategy.realtime import LiveBar, RealtimeMonitor


class FixtureFeed:
    def __init__(self, bars: list[LiveBar]):
        self._bars = bars

    def closed_bars(self, symbol: str, timeframe: str, count: int):
        return self._bars[-count:]


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def zone_payload(zone):
    if zone is None:
        return None
    return {
        "kind": zone.kind,
        "low": zone.low,
        "high": zone.high,
        "touches": zone.touches,
        "center": zone.center,
    }


def indicator_payload(signal):
    values = signal.indicators
    if values is None:
        return None
    return {
        "ema20": values.ema20,
        "ema50": values.ema50,
        "ema200": values.ema200,
        "rsi14": values.rsi14,
        "atr14": values.atr14,
        "adx14": values.adx14,
        "macd": values.macd,
        "macd_signal": values.macd_signal,
        "macd_histogram": values.macd_histogram,
    }


def indicator_context(signal):
    values = signal.indicators
    if values is None:
        return {
            "values": None,
            "trend": "UNAVAILABLE",
            "momentum": "UNAVAILABLE",
            "macd_momentum": "UNAVAILABLE",
            "trend_strength": "UNAVAILABLE",
            "direction": None,
            "confirmations": 0,
            "confirmation_state": "NEUTRAL",
        }
    trend = "UNAVAILABLE"
    if values.ema20 is not None and values.ema50 is not None:
        trend = "BULLISH" if values.ema20 > values.ema50 else "BEARISH" if values.ema20 < values.ema50 else "NEUTRAL"
    momentum = "UNAVAILABLE" if values.rsi14 is None else "BULLISH" if values.rsi14 > 50 else "BEARISH" if values.rsi14 < 50 else "NEUTRAL"
    macd_momentum = "UNAVAILABLE" if values.macd is None or values.macd_signal is None else "BULLISH" if values.macd > values.macd_signal else "BEARISH" if values.macd < values.macd_signal else "NEUTRAL"
    trend_strength = "UNAVAILABLE" if values.adx14 is None else "TRENDING" if values.adx14 >= 25 else "RANGING"
    direction = signal.action if signal.action in {"LONG", "SHORT"} else None
    def matches(bias):
        return (direction == "LONG" and bias == "BULLISH") or (direction == "SHORT" and bias == "BEARISH")
    confirmations = sum(matches(bias) for bias in (trend, momentum, macd_momentum)) if direction else 0
    state = "SUPPORTIVE" if confirmations >= 2 else "MIXED" if confirmations == 1 else "OPPOSED"
    if direction is None:
        state = "NEUTRAL"
    return {
        "values": indicator_payload(signal),
        "trend": trend,
        "momentum": momentum,
        "macd_momentum": macd_momentum,
        "trend_strength": trend_strength,
        "direction": direction,
        "confirmations": confirmations,
        "confirmation_state": state,
    }


def signal_payload(evaluation):
    signal = evaluation.signal
    snapshot = evaluation.snapshot
    forecast_result = evaluation.forecast
    return {
        "signal": signal.action,
        "state": signal.state,
        "reason": signal.reason,
        "price": snapshot.current_close if snapshot else None,
        "bar_time": iso(evaluation.bar_time),
        "structure_bias": signal.structure_bias,
        "zone": zone_payload(signal.zone),
        "entry_reference": signal.entry_reference,
        "stop_reference": signal.stop_reference if signal.action != "WAIT" else None,
        "breakout_state": signal.breakout_state,
        "protection": signal.protection,
        "score": None if signal.score is None else {"total": signal.score.total},
        "indicators": indicator_payload(signal),
        "indicator_context": indicator_context(signal),
        "support": zone_payload(evaluation.support),
        "resistance": zone_payload(evaluation.resistance),
        "forecast": {
            "confidence": forecast_result.confidence if forecast_result else None,
            "horizons": [] if forecast_result is None else [
                {
                    "direction": horizon.direction,
                    "up_probability": horizon.up_probability,
                    "flat_probability": horizon.flat_probability,
                    "down_probability": horizon.down_probability,
                    "expected_return": horizon.expected_return,
                    "expected_close": horizon.expected_close,
                }
                for horizon in forecast_result.horizons
            ],
        },
        "supervisor": None if evaluation.supervisor is None else {
            "action": evaluation.supervisor.action,
            "allowed": evaluation.supervisor.allowed,
            "reasons": list(evaluation.supervisor.reasons),
        },
    }


def main() -> None:
    cases = json.load(sys.stdin)["cases"]
    output = []
    for case in cases:
        bars = [
            LiveBar(
                time=datetime.fromisoformat(row["time"].replace("Z", "+00:00")),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
            for row in case["candles"]
        ]
        monitor = RealtimeMonitor(
            FixtureFeed(bars),
            case["symbol"],
            case["timeframe"],
            lookback=len(bars),
        )
        evaluation = monitor.evaluate_once(now=bars[-1].time)
        if evaluation is None:
            raise RuntimeError(f"oracle produced no evaluation for {case['name']}")
        output.append({"name": case["name"], **signal_payload(evaluation)})
    json.dump(output, sys.stdout, separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    main()
