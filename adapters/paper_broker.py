"""Deterministic broker simulator for paper/demo execution tests.

This adapter is intentionally disconnected from MetaTrader5 and any real
broker. It models execution semantics needed to exercise order-state,
idempotency, reconciliation, recovery, and feed-integrity layers.

Chaos is explicit and deterministic. The simulator never sends network traffic
and cannot place a real order.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Iterable


LONG = "LONG"
SHORT = "SHORT"

FILLED = "FILLED"
PARTIALLY_FILLED = "PARTIALLY_FILLED"
REJECTED = "REJECTED"
UNKNOWN = "UNKNOWN"


class ChaosScenario(str, Enum):
    NORMAL = "NORMAL"
    ROUNDED_VOLUME = "ROUNDED_VOLUME"
    REJECT_THREE_TIMES = "REJECT_THREE_TIMES"
    OUT_OF_ORDER_CANDLES = "OUT_OF_ORDER_CANDLES"
    TEMPORARY_MISSING_CANDLES = "TEMPORARY_MISSING_CANDLES"


@dataclass(frozen=True)
class PaperOrderRequest:
    client_order_id: str
    symbol: str
    direction: str
    quantity: float
    price: float
    submitted_at: datetime


@dataclass(frozen=True)
class PaperOrderSnapshot:
    client_order_id: str
    symbol: str
    direction: str
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float | None
    status: str
    updated_at: datetime

    @property
    def remaining_quantity(self) -> float:
        return self.requested_quantity - self.filled_quantity


@dataclass(frozen=True)
class PaperPositionSnapshot:
    symbol: str
    net_quantity: float
    average_price: float


class PaperBrokerSimulator:
    """Deterministic broker-like state machine for paper/demo validation."""

    def __init__(
        self,
        *,
        fill_fraction: float = 1.0,
        fill_price_offset: float = 0.0,
        reject_next: bool = False,
        timeout_after_accept_next: bool = False,
    ) -> None:
        if not isfinite(fill_fraction) or not 0.0 < fill_fraction <= 1.0:
            raise ValueError("fill_fraction must be finite and in (0, 1]")
        if not isfinite(fill_price_offset):
            raise ValueError("fill_price_offset must be finite")
        self._fill_fraction = fill_fraction
        self._fill_price_offset = fill_price_offset
        self._reject_next = bool(reject_next)
        self._reject_remaining = 0
        self._timeout_after_accept_next = bool(timeout_after_accept_next)
        self._volume_noise = 0.0
        self._connected = True
        self._orders: dict[str, PaperOrderSnapshot] = {}
        self._positions: dict[str, PaperPositionSnapshot] = {}

    @property
    def connected(self) -> bool:
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> None:
        self._connected = True

    def configure_next_rejection(self) -> None:
        self._reject_next = True

    def configure_rejections(self, count: int = 3) -> None:
        """Reject the next ``count`` distinct submissions for a client order."""
        if count < 1:
            raise ValueError("count must be >= 1")
        self._reject_remaining = count

    def configure_next_timeout_after_accept(self) -> None:
        self._timeout_after_accept_next = True

    def configure_volume_noise(self, noise: float = 1e-5) -> None:
        """Add deterministic broker-reporting noise to position snapshots."""
        if not isfinite(noise) or noise < 0:
            raise ValueError("noise must be finite and >= 0")
        self._volume_noise = noise

    def submit(
        self,
        request: PaperOrderRequest,
        *,
        scenario: ChaosScenario = ChaosScenario.NORMAL,
    ) -> PaperOrderSnapshot:
        """Submit one request with deterministic broker-like semantics.

        ``REJECT_THREE_TIMES`` models repeated broker rejection without ever
        fabricating a successful fill. The caller decides whether and when to
        retry; the simulator itself does not implement a retry loop.

        A timeout-after-accept records the order as FILLED and then raises
        ``TimeoutError`` so recovery must reconcile before any retry.
        """
        self._validate_request(request)
        if not self._connected:
            raise ConnectionError("paper broker is disconnected")

        existing = self._orders.get(request.client_order_id)
        if existing is not None:
            return existing

        reject = self._reject_next
        if scenario is ChaosScenario.REJECT_THREE_TIMES:
            if self._reject_remaining == 0:
                self._reject_remaining = 3
            reject = True

        if reject:
            self._reject_next = False
            if self._reject_remaining > 0:
                self._reject_remaining -= 1
            rejected = PaperOrderSnapshot(
                client_order_id=request.client_order_id,
                symbol=request.symbol,
                direction=request.direction,
                requested_quantity=request.quantity,
                filled_quantity=0.0,
                average_fill_price=None,
                status=REJECTED,
                updated_at=request.submitted_at,
            )
            # A rejection is intentionally not terminal simulator state: a
            # new client request with a new id may still be tested independently.
            return rejected

        filled_quantity = request.quantity * self._fill_fraction
        if filled_quantity <= 0.0:
            raise RuntimeError("simulator produced zero fill")
        status = FILLED if filled_quantity == request.quantity else PARTIALLY_FILLED
        fill_price = request.price + self._fill_price_offset
        snapshot = PaperOrderSnapshot(
            client_order_id=request.client_order_id,
            symbol=request.symbol,
            direction=request.direction,
            requested_quantity=request.quantity,
            filled_quantity=filled_quantity,
            average_fill_price=fill_price,
            status=status,
            updated_at=request.submitted_at,
        )
        self._orders[request.client_order_id] = snapshot
        self._apply_fill(snapshot)

        if self._timeout_after_accept_next:
            self._timeout_after_accept_next = False
            raise TimeoutError("submission response lost after broker acceptance")
        return snapshot

    def get_order(self, client_order_id: str) -> PaperOrderSnapshot | None:
        if not self._connected:
            raise ConnectionError("paper broker is disconnected")
        return self._orders.get(client_order_id)

    def list_orders(self) -> tuple[PaperOrderSnapshot, ...]:
        return tuple(self._orders.values())

    def positions(self, *, scenario: ChaosScenario = ChaosScenario.NORMAL) -> tuple[PaperPositionSnapshot, ...]:
        """Return broker positions, optionally with deterministic volume noise."""
        positions = tuple(self._positions.values())
        if scenario is not ChaosScenario.ROUNDED_VOLUME:
            return positions
        return tuple(
            replace(position, net_quantity=position.net_quantity + self._volume_noise)
            for position in positions
        )

    @staticmethod
    def distort_candles(candles: Iterable[dict], scenario: ChaosScenario) -> list[dict]:
        """Inject deterministic out-of-order or temporary missing bars."""
        data = [dict(candle) for candle in candles]
        if scenario is ChaosScenario.OUT_OF_ORDER_CANDLES and len(data) >= 3:
            data[1], data[2] = data[2], data[1]
        elif scenario is ChaosScenario.TEMPORARY_MISSING_CANDLES and len(data) >= 3:
            data.pop(len(data) // 2)
        return data

    def _apply_fill(self, order: PaperOrderSnapshot) -> None:
        if order.average_fill_price is None or order.filled_quantity <= 0:
            return
        signed_quantity = order.filled_quantity if order.direction == LONG else -order.filled_quantity
        current = self._positions.get(order.symbol)
        if current is None:
            self._positions[order.symbol] = PaperPositionSnapshot(
                symbol=order.symbol,
                net_quantity=signed_quantity,
                average_price=order.average_fill_price,
            )
            return

        new_quantity = current.net_quantity + signed_quantity
        if new_quantity == 0.0:
            self._positions.pop(order.symbol, None)
            return

        same_direction = current.net_quantity != 0.0 and (current.net_quantity > 0) == (signed_quantity > 0)
        if same_direction:
            total_abs = abs(current.net_quantity) + abs(signed_quantity)
            weighted_price = (
                abs(current.net_quantity) * current.average_price
                + abs(signed_quantity) * order.average_fill_price
            ) / total_abs
            self._positions[order.symbol] = replace(
                current,
                net_quantity=new_quantity,
                average_price=weighted_price,
            )
            return

        # Opposite-side fills reduce an existing position. The remaining
        # quantity keeps the original entry average; a true reversal starts a
        # fresh position at the new fill price.
        if (current.net_quantity > 0) == (new_quantity > 0):
            self._positions[order.symbol] = replace(current, net_quantity=new_quantity)
        else:
            self._positions[order.symbol] = PaperPositionSnapshot(
                symbol=order.symbol,
                net_quantity=new_quantity,
                average_price=order.average_fill_price,
            )

    @staticmethod
    def _validate_request(request: PaperOrderRequest) -> None:
        if not request.client_order_id:
            raise ValueError("client_order_id must not be empty")
        if not request.symbol:
            raise ValueError("symbol must not be empty")
        if request.direction not in {LONG, SHORT}:
            raise ValueError("direction must be LONG or SHORT")
        if not isfinite(request.quantity) or request.quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        if not isfinite(request.price) or request.price <= 0:
            raise ValueError("price must be finite and > 0")
        if request.submitted_at.tzinfo is None or request.submitted_at.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware")
        if request.submitted_at.astimezone(timezone.utc).utcoffset() != timezone.utc.utcoffset(request.submitted_at):
            raise ValueError("submitted_at must use UTC")


__all__ = [
    "LONG",
    "SHORT",
    "FILLED",
    "PARTIALLY_FILLED",
    "REJECTED",
    "UNKNOWN",
    "ChaosScenario",
    "PaperOrderRequest",
    "PaperOrderSnapshot",
    "PaperPositionSnapshot",
    "PaperBrokerSimulator",
]
