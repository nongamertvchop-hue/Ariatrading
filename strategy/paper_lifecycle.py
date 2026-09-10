"""Formal session-level lifecycle for realtime paper trading.

OrderStateMachine owns broker-order state.  This companion machine owns the
human-readable runtime lifecycle so a dashboard and recovery procedure can
unambiguously show FLAT/SIGNAL/APPROVED/OPEN/EXIT_PENDING/CLOSED/HALT.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PaperLifecycleState(str, Enum):
    FLAT = "FLAT"
    SIGNAL = "SIGNAL"
    APPROVED = "APPROVED"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OPEN = "OPEN"
    EXIT_PENDING = "EXIT_PENDING"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"
    HALT = "HALT"


_ALLOWED = {
    PaperLifecycleState.FLAT: {PaperLifecycleState.SIGNAL, PaperLifecycleState.HALT},
    PaperLifecycleState.SIGNAL: {PaperLifecycleState.APPROVED, PaperLifecycleState.FLAT, PaperLifecycleState.HALT},
    PaperLifecycleState.APPROVED: {PaperLifecycleState.SUBMITTING, PaperLifecycleState.HALT},
    PaperLifecycleState.SUBMITTING: {
        PaperLifecycleState.ACKNOWLEDGED,
        PaperLifecycleState.OPEN,
        PaperLifecycleState.UNKNOWN,
        PaperLifecycleState.FLAT,
        PaperLifecycleState.HALT,
    },
    PaperLifecycleState.ACKNOWLEDGED: {
        PaperLifecycleState.OPEN,
        PaperLifecycleState.UNKNOWN,
        PaperLifecycleState.HALT,
    },
    PaperLifecycleState.OPEN: {PaperLifecycleState.EXIT_PENDING, PaperLifecycleState.HALT},
    PaperLifecycleState.EXIT_PENDING: {
        PaperLifecycleState.CLOSED,
        PaperLifecycleState.OPEN,
        PaperLifecycleState.UNKNOWN,
        PaperLifecycleState.HALT,
    },
    PaperLifecycleState.CLOSED: {PaperLifecycleState.FLAT, PaperLifecycleState.SIGNAL, PaperLifecycleState.HALT},
    PaperLifecycleState.UNKNOWN: {
        PaperLifecycleState.ACKNOWLEDGED,
        PaperLifecycleState.OPEN,
        PaperLifecycleState.CLOSED,
        PaperLifecycleState.FLAT,
        PaperLifecycleState.HALT,
    },
    PaperLifecycleState.HALT: {PaperLifecycleState.HALT},
}


@dataclass(frozen=True)
class LifecycleTransition:
    accepted: bool
    state: PaperLifecycleState
    reason: str


class PaperLifecycleMachine:
    def __init__(self, state: PaperLifecycleState = PaperLifecycleState.FLAT) -> None:
        self._state = state

    @property
    def state(self) -> PaperLifecycleState:
        return self._state

    def transition(self, new_state: PaperLifecycleState) -> LifecycleTransition:
        if new_state == self._state:
            return LifecycleTransition(True, self._state, "state unchanged")
        if new_state not in _ALLOWED[self._state]:
            return LifecycleTransition(
                False,
                self._state,
                f"invalid lifecycle transition {self._state.value} -> {new_state.value}",
            )
        self._state = new_state
        return LifecycleTransition(True, self._state, "transition accepted")

    def restore(self, state: PaperLifecycleState) -> None:
        if not isinstance(state, PaperLifecycleState):
            raise ValueError("state must be a PaperLifecycleState")
        self._state = state


__all__ = ["LifecycleTransition", "PaperLifecycleMachine", "PaperLifecycleState"]
