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
    """Cluster nearby prices without allowing a chain to grow indefinitely."""
    if tolerance <= 0:
        raise ValueError("tolerance must be > 0")
    clusters: list[list[float]] = []
    for price in sorted(prices):
        if not clusters:
            clusters.append([price])
            continue
        anchor = clusters[-1][0]
        if price - anchor <= tolerance:
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
    """Turn repeated reaction prices into zones.

    This public helper accepts prices only, so every supplied price is treated
    as an already-independent reaction. The candle-aware find_* functions
    apply the temporal separation rule before calling it.
    """
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


def _build_swing_zones(
    swings: list[tuple[int, float]],
    kind: str,
    tolerance: float,
    min_touches: int,
    min_reaction_gap: int,
) -> list[PriceZone]:
    """Build zones while requiring touches to be separated in time."""
    if min_reaction_gap < 1:
        raise ValueError("min_reaction_gap must be >= 1")

    zones: list[PriceZone] = []
    for cluster in _cluster([price for _, price in swings], tolerance):
        cluster_swings = [
            swing for swing in swings
            if any(price == swing[1] for price in cluster)
        ]
        cluster_swings.sort(key=lambda item: item[0])

        selected: list[tuple[int, float]] = []
        for swing in cluster_swings:
            if not selected or swing[0] - selected[-1][0] >= min_reaction_gap:
                selected.append(swing)

        if len(selected) < min_touches:
            continue

        prices = [price for _, price in selected]
        zones.append(
            PriceZone(
                low=min(prices) - tolerance,
                high=max(prices) + tolerance,
                kind=kind,
                touches=len(selected),
            )
        )
    return zones


def find_support_zones(
    candles: list[dict],
    strength: int = 2,
    tolerance: float = 0.0010,
    min_touches: int = 2,
    min_reaction_gap: int = 2,
) -> list[PriceZone]:
    swings = confirmed_swing_lows(candles, strength)
    return _build_swing_zones(
        swings, SUPPORT, tolerance, min_touches, min_reaction_gap
    )


def find_resistance_zones(
    candles: list[dict],
    strength: int = 2,
    tolerance: float = 0.0010,
    min_touches: int = 2,
    min_reaction_gap: int = 2,
) -> list[PriceZone]:
    swings = confirmed_swing_highs(candles, strength)
    return _build_swing_zones(
        swings, RESISTANCE, tolerance, min_touches, min_reaction_gap
    )
