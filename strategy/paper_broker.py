"""Deterministic paper-broker chaos simulator for resilience testing.

This module is deliberately paper-only. It never connects to a broker and never
places real orders. Chaos is explicit and reproducible so recovery and
reconciliation code can be tested against hostile-but-plausible inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .position_reconciliation import PositionSnapshot


class ChaosScenario(str, Enum):
    NORMAL = "NORMAL"
    ROUNDED_VOLUME = "ROUNDED_VOLUME"
    REJECT_MARKET_ORDER_THREE_TIMES = "REJECT_MARKET_ORDER_THREE_TIMES"
    OUT_OF_ORDER_CANDLES = "OUT_OF_ORDER_CANDLES"
    TEMPORARY_MISSING_CANDLES = "TEMPORARY_MISSING_CANDLES"


@dataclass(frozen=True)
class PaperOrderResult:
    accepted: bool
    status: str
    attempts: int
    broker_order_id: str | None
    filled_quantity: float
    reason: str


@dataclass(frozen=True)
class PaperBrokerConfig:
    symbol: str = "EURUSD"
    volume_step: float = 0.01
    price_digits: int = 5
    reject_attempts: int = 3
    missing_every: int = 5

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.volume_step <= 0:
            raise ValueError("volume_step must be > 0")
        if self.price_digits < 0:
            raise ValueError("price_digits must be >= 0")
        if self.reject_attempts < 1:
            raise ValueError("reject_attempts must be >= 1")
        if self.missing_every < 2:
            raise ValueError("missing_every must be >= 2")


class PaperBroker:
    """Small deterministic simulator used by resilience tests only."""

    def __init__(self, config: PaperBrokerConfig | None = None) -> None:
        self.config = config or PaperBrokerConfig()
        self._attempts_by_client_order: dict[str, int] = {}
        self._positions: dict[str, PositionSnapshot] = {}

    def submit_market_order(
        self,
        *,
        client_order_id: str,
        direction: str,
        quantity: float,
        scenario: ChaosScenario = ChaosScenario.NORMAL,
        price: float = 1.10000,
    ) -> PaperOrderResult:
        """Return deterministic paper execution outcomes under a chaos scenario."""
        if not client_order_id:
            raise ValueError("client_order_id must not be empty")
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if price <= 0:
            raise ValueError("price must be > 0")

        attempt = self._attempts_by_client_order.get(client_order_id, 0) + 1
        self._attempts_by_client_order[client_order_id] = attempt

        if scenario is ChaosScenario.REJECT_MARKET_ORDER_THREE_TIMES and attempt <= self.config.reject_attempts:
            return PaperOrderResult(False, "REJECTED", attempt, None, 0.0, "simulated broker rejection")

        filled_quantity = quantity
        if scenario is ChaosScenario.ROUNDED_VOLUME:
            steps = round(quantity / self.config.volume_step)
            filled_quantity = round(steps * self.config.volume_step, 12)
            # Deliberately emulate a broker representation artifact without
            # changing the economic quantity represented by the volume step.
            filled_quantity = float(f"{filled_quantity:.12f}")

        broker_order_id = f"PAPER-{client_order_id}"
        position = PositionSnapshot(
            symbol=self.config.symbol,
            direction=direction,
            quantity=filled_quantity,
            position_id=broker_order_id,
            average_entry_price=round(price, self.config.price_digits),
        )
        self._positions[broker_order_id] = position
        return PaperOrderResult(True, "FILLED", attempt, broker_order_id, filled_quantity, "simulated fill")

    def positions(self, scenario: ChaosScenario = ChaosScenario.NORMAL) -> list[PositionSnapshot]:
        """Return the broker snapshot, optionally with a deterministic disturbance."""
        positions = list(self._positions.values())
        if scenario is ChaosScenario.ROUNDED_VOLUME:
            return [
                PositionSnapshot(
                    symbol=position.symbol,
                    direction=position.direction,
                    quantity=float(f"{position.quantity + 1e-5:.12f}"),
                    position_id=position.position_id,
                    average_entry_price=position.average_entry_price,
                )
                for position in positions
            ]
        return positions

    def distort_candles(
        self,
        candles: Iterable[dict],
        scenario: ChaosScenario,
    ) -> list[dict]:
        """Inject out-of-order or temporary-gap candle-feed failures."""
        data = [dict(candle) for candle in candles]
        if scenario is ChaosScenario.OUT_OF_ORDER_CANDLES and len(data) >= 3:
            data[1], data[2] = data[2], data[1]
        elif scenario is ChaosScenario.TEMPORARY_MISSING_CANDLES and len(data) >= self.config.missing_every:
            data.pop(self.config.missing_every - 1)
        return data

    def reset(self) -> None:
        """Reset all simulator state between chaos experiments."""
        self._attempts_by_client_order.clear()
        self._positions.clear()


__all__ = ["ChaosScenario", "PaperBroker", "PaperBrokerConfig", "PaperOrderResult"]
