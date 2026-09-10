from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True)
class ExitPair:
    stop_loss: float
    take_profit: float

    def validate(self, *, side: str, entry: float) -> None:
        if entry <= 0 or self.stop_loss <= 0 or self.take_profit <= 0:
            raise ValueError("entry and exits must be > 0")
        if side == "LONG" and not (self.stop_loss < entry < self.take_profit):
            raise ValueError("LONG requires stop < entry < take-profit")
        if side == "SHORT" and not (self.take_profit < entry < self.stop_loss):
            raise ValueError("SHORT requires take-profit < entry < stop")
        if side not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    symbol: str
    side: str
    order_type: OrderType
    quantity: float
    entry: float
    exits: ExitPair

    def validate(self) -> None:
        if not self.intent_id or not self.symbol:
            raise ValueError("intent_id and symbol are required")
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        self.exits.validate(side=self.side, entry=self.entry)

    @property
    def oco_group(self) -> str:
        """Stable local OCO identity; broker-side OCO semantics remain adapter-specific."""
        return f"oco:{self.intent_id}"
