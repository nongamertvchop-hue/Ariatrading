"""Confirmed support/resistance zones for the two basic price-action setups.

This module is deliberately indicator-free. It works from OHLC candles only.
The key rule is that a swing is usable only after its confirmation candles
have closed, so a live/backtest engine does not accidentally use future data.
"""

from dataclasses import dataclass


SUPPORT = "SUPPORT"
RESISTANCE = "RESISTANCE"


@dataclass(frozen=True)
class PriceZone:
    """A horizontal price zone built from repeated swing reactions."""

    low: float
    high: float
    kind: str
    touches: int

    @property
    def center(self) -> float:
        return (self.low + self.high) / 2


def confirmed_swing_lows(candles: list[dict], strength: int = 2) -> list[tuple[int, float]]:
    """Return (swing_index, low) after the swing has been confirmed."""
    if strength < 1:
        raise ValueError("strength must be >= 1")
    lows = [float(c["low"]) for c in candles]
    result: list[tuple[int, float]] = []
    for i in range(strength, len(lows) - strength):
        window = lows[i - strength : i + strength + 1]
        if lows[i] == min(window) and window.count(lows[i]) == 1:
            result.append((i, lows[i]))
    return result


def confirmed_swing_highs(candles: list[dict], strength: int = 2) -> list[tuple[int, float]]:
    """Return (swing_index, high) after the swing has been confirmed."""
    if strength < 1:
        raise ValueError("strength must be >= 1")
    highs = [float(c["high"]) for c in candles]
    result: list[tuple[int, float]] = []
    for i in range(strength, len(highs) - strength):
        window = highs[i - strength : i + strength + 1]
        if highs[i] == max(window) and window.count(highs[i]) == 1:
            result.append((i, highs[i]))
    return result


def _cluster(prices: list[float], tolerance: float) -> list[list[float]]:
    if tolerance <= 0:
        raise ValueError("tolerance must be > 0")
    clusters: list[list[float]] = []
    for price in sorted(prices):
        if not clusters:
            clusters.append([price])
            continue
        center = sum(clusters[-1]) / len(clusters[-1])
        if abs(price - center) <= tolerance:
            clusters[-1].append(price)
        else:
            clusters.append([price])
    return clusters


def build_zones(
    prices: list[float],
    kind: str,
    tolerance: float = 0.0010,
    min_touches: int = 2,
) -> list[PriceZone]:
    """Turn repeated reaction prices into zones."""
    if kind not in {SUPPORT, RESISTANCE}:
        raise ValueError("kind must be SUPPORT or RESISTANCE")
    if min_touches < 1:
        raise ValueError("min_touches must be >= 1")

    zones: list[PriceZone] = []
    for cluster in _cluster(prices, tolerance):
        if len(cluster) < min_touches:
            continue
        zones.append(
            PriceZone(
                low=min(cluster) - tolerance,
                high=max(cluster) + tolerance,
                kind=kind,
                touches=len(cluster),
            )
        )
    return zones


def find_support_zones(
    candles: list[dict],
    strength: int = 2,
    tolerance: float = 0.0010,
    min_touches: int = 2,
) -> list[PriceZone]:
    swings = confirmed_swing_lows(candles, strength)
    return build_zones([price for _, price in swings], SUPPORT, tolerance, min_touches)


def find_resistance_zones(
    candles: list[dict],
    strength: int = 2,
    tolerance: float = 0.0010,
    min_touches: int = 2,
) -> list[PriceZone]:
    swings = confirmed_swing_highs(candles, strength)
    return build_zones([price for _, price in swings], RESISTANCE, tolerance, min_touches)
