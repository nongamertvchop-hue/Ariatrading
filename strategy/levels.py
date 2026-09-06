"""Support and resistance detection from raw price data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceLevel:
    price: float
    kind: str
    touches: int


def find_swing_lows(candles: list[dict], strength: int = 2) -> list[float]:
    """Return local lows that are lower than nearby candles."""
    if strength < 1:
        raise ValueError("strength must be >= 1")
    lows = [float(c["low"]) for c in candles]
    result = []
    for i in range(strength, len(lows) - strength):
        window = lows[i - strength : i + strength + 1]
        if lows[i] == min(window) and window.count(lows[i]) == 1:
            result.append(lows[i])
    return result


def find_swing_highs(candles: list[dict], strength: int = 2) -> list[float]:
    """Return local highs that are higher than nearby candles."""
    if strength < 1:
        raise ValueError("strength must be >= 1")
    highs = [float(c["high"]) for c in candles]
    result = []
    for i in range(strength, len(highs) - strength):
        window = highs[i - strength : i + strength + 1]
        if highs[i] == max(window) and window.count(highs[i]) == 1:
            result.append(highs[i])
    return result


def cluster_levels(prices: list[float], tolerance: float) -> list[tuple[float, int]]:
    """Group nearby prices into zones and return (center, touch_count)."""
    if tolerance <= 0:
        raise ValueError("tolerance must be > 0")
    if not prices:
        return []

    clusters: list[list[float]] = []
    for price in sorted(prices):
        if not clusters or price - sum(clusters[-1]) / len(clusters[-1]) > tolerance:
            clusters.append([price])
        else:
            clusters[-1].append(price)

    return [(sum(cluster) / len(cluster), len(cluster)) for cluster in clusters]


def find_supports(candles: list[dict], strength: int = 2, tolerance: float = 0.0010) -> list[PriceLevel]:
    return [PriceLevel(price, "SUPPORT", touches) for price, touches in cluster_levels(find_swing_lows(candles, strength), tolerance) if touches >= 2]


def find_resistances(candles: list[dict], strength: int = 2, tolerance: float = 0.0010) -> list[PriceLevel]:
    return [PriceLevel(price, "RESISTANCE", touches) for price, touches in cluster_levels(find_swing_highs(candles, strength), tolerance) if touches >= 2]
