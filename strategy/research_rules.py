"""Runtime research and innovation contract for Ariatrading.

The project rules are documented in docs/RESEARCH_AND_INNOVATION_RULES.md.
This module turns the most important safety/research boundaries into executable
checks so strategy evaluation cannot silently drift into an unsupported mode.
"""

from dataclasses import dataclass

RULESET_VERSION = "2026-09-10-r1"
PAPER_MODE = "paper"
DEMO_MODE = "demo"
LIVE_MODE = "live"

ALLOWED_RESEARCH_MODES = frozenset({PAPER_MODE, DEMO_MODE})


@dataclass(frozen=True)
class ResearchContract:
    """Immutable runtime contract describing the allowed development mode."""

    ruleset_version: str = RULESET_VERSION
    execution_mode: str = PAPER_MODE
    innovation_policy: str = "hypothesis-test-evidence"
    future_data_allowed: bool = False
    strategy_may_create_new_direction: bool = False

    def __post_init__(self) -> None:
        if self.execution_mode not in ALLOWED_RESEARCH_MODES:
            raise ValueError(
                "Ariatrading research contract is fail-closed: "
                f"unsupported execution mode {self.execution_mode!r}"
            )
        if self.future_data_allowed:
            raise ValueError("future data is prohibited by the research contract")
        if self.strategy_may_create_new_direction:
            raise ValueError(
                "context/ML challengers may not create a new trading direction"
            )

    @property
    def safe(self) -> bool:
        return self.execution_mode in ALLOWED_RESEARCH_MODES


def enforce_research_contract(execution_mode: str = PAPER_MODE) -> ResearchContract:
    """Return the runtime contract or fail closed for unsupported execution."""
    contract = ResearchContract(execution_mode=execution_mode)
    if not contract.safe:
        raise RuntimeError("research contract is not safe")
    return contract


__all__ = [
    "ALLOWED_RESEARCH_MODES",
    "DEMO_MODE",
    "LIVE_MODE",
    "PAPER_MODE",
    "RULESET_VERSION",
    "ResearchContract",
    "enforce_research_contract",
]
