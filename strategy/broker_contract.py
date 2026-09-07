"""Normalized broker-symbol contract validation for execution boundaries.

This module only validates metadata and proposed order parameters. It never
places, modifies, or cancels broker orders and has no network side effects.
"""

from dataclasses import dataclass
from math import isclose, isfinite


@dataclass(frozen=True)
class SymbolContract:
    """Normalized symbol constraints supplied by an external adapter."""

    symbol: str
    digits: int
    point: float
    volume_min: float
    volume_max: float
    volume_step: float

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.digits < 0:
            raise ValueError("digits must be >= 0")
        for name, value in {
            "point": self.point,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
        }.items():
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max must be >= volume_min")


@dataclass(frozen=True)
class ContractValidation:
    allowed: bool
    reason: str


def _price_is_precise(price: float, digits: int) -> bool:
    quantum = 10.0 ** (-digits)
    rounded = round(price, digits)
    return isclose(price, rounded, rel_tol=0.0, abs_tol=quantum * 1e-9)


def validate_order_contract(
    contract: SymbolContract,
    *,
    symbol: str,
    price: float,
    quantity: float,
) -> ContractValidation:
    """Validate symbol identity, price precision and volume constraints."""
    if symbol != contract.symbol:
        return ContractValidation(False, "order symbol differs from broker contract")
    if not isfinite(price) or price <= 0:
        return ContractValidation(False, "price must be finite and > 0")
    if not _price_is_precise(price, contract.digits):
        return ContractValidation(False, "price exceeds broker symbol precision")
    if not isfinite(quantity) or quantity <= 0:
        return ContractValidation(False, "quantity must be finite and > 0")
    if quantity < contract.volume_min:
        return ContractValidation(False, "quantity is below broker minimum")
    if quantity > contract.volume_max:
        return ContractValidation(False, "quantity exceeds broker maximum")

    steps = (quantity - contract.volume_min) / contract.volume_step
    if not isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9):
        return ContractValidation(False, "quantity does not match broker volume step")

    return ContractValidation(True, "broker symbol contract passed")


__all__ = ["ContractValidation", "SymbolContract", "validate_order_contract"]
