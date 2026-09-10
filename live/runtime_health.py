"""Operator-facing runtime health evaluation with explicit fail-closed states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RuntimeHealth:
    state: HealthState
    heartbeat_age_seconds: float
    market_data_age_seconds: float
    reason: str


def evaluate_health(
    *,
    heartbeat_age_seconds: float,
    market_data_age_seconds: float,
    max_heartbeat_age_seconds: float,
    max_market_data_age_seconds: float,
    blocked: bool = False,
    error: bool = False,
) -> RuntimeHealth:
    """Map observable runtime conditions to a small, stable operational contract."""
    values = (
        heartbeat_age_seconds,
        market_data_age_seconds,
        max_heartbeat_age_seconds,
        max_market_data_age_seconds,
    )
    if not all(isinstance(value, (int, float)) for value in values):
        raise ValueError("health metrics must be numeric")
    if any(value < 0 for value in values) or max_heartbeat_age_seconds <= 0 or max_market_data_age_seconds <= 0:
        raise ValueError("health ages/limits must be non-negative and limits must be positive")
    if error:
        return RuntimeHealth(HealthState.ERROR, heartbeat_age_seconds, market_data_age_seconds, "runtime error requires operator attention")
    if blocked:
        return RuntimeHealth(HealthState.BLOCKED, heartbeat_age_seconds, market_data_age_seconds, "runtime safety gate is blocking new execution")
    if heartbeat_age_seconds > max_heartbeat_age_seconds or market_data_age_seconds > max_market_data_age_seconds:
        return RuntimeHealth(HealthState.DEGRADED, heartbeat_age_seconds, market_data_age_seconds, "runtime or market data freshness exceeded limit")
    return RuntimeHealth(HealthState.HEALTHY, heartbeat_age_seconds, market_data_age_seconds, "runtime health within limits")
