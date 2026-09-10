"""Read-only broker evidence checks for unresolved execution intents.

This module never sends, modifies, or closes an order. It only inspects MT5
positions/orders/deals and returns evidence when the broker records contain the
exact strategy-owned intent token plus matching symbol, direction, and volume.
Ambiguous or weak matches are deliberately not considered proof.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import isclose
from typing import Any


def _direction_matches(mt5: Any, value: Any, direction: str, *, deal: bool = False) -> bool:
    expected = direction.upper()
    if deal:
        buy = getattr(mt5, "DEAL_TYPE_BUY", 0)
        sell = getattr(mt5, "DEAL_TYPE_SELL", 1)
    else:
        buy = getattr(mt5, "ORDER_TYPE_BUY", 0)
        sell = getattr(mt5, "ORDER_TYPE_SELL", 1)
    if expected == "BUY":
        return int(value) == int(buy)
    if expected == "SELL":
        return int(value) == int(sell)
    return False


def _comment_matches(comment: Any, token: str) -> bool:
    return token in str(comment or "")


def _volume_matches(value: Any, expected: float) -> bool:
    try:
        return isclose(float(value), float(expected), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return False


def find_execution_evidence(
    *,
    mt5: Any,
    magic_number: int,
    intent_id: str,
    symbol: str,
    direction: str,
    volume: float,
    since: datetime,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return strong broker evidence for one unresolved intent.

    Every returned record has the intent token, strategy magic, symbol,
    direction and requested volume. MT5 history APIs returning None are treated
    as errors because incomplete broker history must never be interpreted as
    evidence that an order did not execute.
    """
    if mt5 is None:
        raise RuntimeError("MT5 module unavailable")
    if since.tzinfo is None or since.utcoffset() is None:
        raise ValueError("since must be timezone-aware")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if current < since:
        raise ValueError("now must be >= since")

    token = f"Aria-{intent_id[:12]}"
    expected_symbol = symbol.strip().upper()
    evidence: list[dict[str, Any]] = []

    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        raise RuntimeError(f"MT5 positions_get failed: {mt5.last_error()}")
    for position in positions:
        if int(getattr(position, "magic", 0)) != int(magic_number):
            continue
        if str(getattr(position, "symbol", "")).upper() != expected_symbol:
            continue
        if not _comment_matches(getattr(position, "comment", ""), token):
            continue
        if not _direction_matches(mt5, getattr(position, "type", -1), direction):
            continue
        if not _volume_matches(getattr(position, "volume", 0.0), volume):
            continue
        evidence.append({
            "kind": "position",
            "ticket": int(getattr(position, "ticket", 0)),
            "position_id": int(getattr(position, "identifier", getattr(position, "ticket", 0))),
            "symbol": expected_symbol,
        })

    orders = mt5.history_orders_get(since, current)
    if orders is None:
        raise RuntimeError(f"MT5 history_orders_get failed: {mt5.last_error()}")
    for order in orders:
        if int(getattr(order, "magic", 0)) != int(magic_number):
            continue
        if str(getattr(order, "symbol", "")).upper() != expected_symbol:
            continue
        if not _comment_matches(getattr(order, "comment", ""), token):
            continue
        if not _direction_matches(mt5, getattr(order, "type", -1), direction):
            continue
        requested_volume = getattr(order, "volume_initial", getattr(order, "volume_current", 0.0))
        if not _volume_matches(requested_volume, volume):
            continue
        evidence.append({
            "kind": "order",
            "ticket": int(getattr(order, "ticket", 0)),
            "position_id": int(getattr(order, "position_id", 0)),
            "symbol": expected_symbol,
        })

    deals = mt5.history_deals_get(since, current)
    if deals is None:
        raise RuntimeError(f"MT5 history_deals_get failed: {mt5.last_error()}")
    for deal in deals:
        if int(getattr(deal, "magic", 0)) != int(magic_number):
            continue
        if str(getattr(deal, "symbol", "")).upper() != expected_symbol:
            continue
        if not _comment_matches(getattr(deal, "comment", ""), token):
            continue
        if not _direction_matches(mt5, getattr(deal, "type", -1), direction, deal=True):
            continue
        if not _volume_matches(getattr(deal, "volume", 0.0), volume):
            continue
        evidence.append({
            "kind": "deal",
            "ticket": int(getattr(deal, "ticket", 0)),
            "order": int(getattr(deal, "order", 0)),
            "position_id": int(getattr(deal, "position_id", 0)),
            "symbol": expected_symbol,
        })

    return evidence


def is_unambiguous_execution(evidence: list[dict[str, Any]]) -> bool:
    """Require broker evidence to collapse to one execution identity.

    Multiple records are normal for one broker execution (order + deal + open
    position), so they are accepted only when they share a non-zero position ID
    or order ticket. Otherwise the result remains ambiguous.
    """
    if not evidence:
        return False
    position_ids = {int(item.get("position_id", 0)) for item in evidence if int(item.get("position_id", 0))}
    order_ids = {int(item.get("order", item.get("ticket", 0))) for item in evidence if int(item.get("order", item.get("ticket", 0)))}
    if len(position_ids) == 1:
        return True
    if len(order_ids) == 1:
        return True
    return len(evidence) == 1
