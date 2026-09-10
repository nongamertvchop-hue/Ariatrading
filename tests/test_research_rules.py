import pytest

from strategy.research_rules import (
    DEMO_MODE,
    LIVE_MODE,
    PAPER_MODE,
    RULESET_VERSION,
    ResearchContract,
    enforce_research_contract,
)


def test_research_contract_defaults_to_paper_and_forbids_future_data() -> None:
    contract = enforce_research_contract()
    assert contract.execution_mode == PAPER_MODE
    assert contract.ruleset_version == RULESET_VERSION
    assert contract.future_data_allowed is False
    assert contract.strategy_may_create_new_direction is False
    assert contract.safe is True


def test_demo_mode_is_allowed() -> None:
    contract = enforce_research_contract(DEMO_MODE)
    assert contract.safe is True


def test_live_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="fail-closed"):
        enforce_research_contract(LIVE_MODE)


def test_contract_rejects_future_data() -> None:
    with pytest.raises(ValueError, match="future data"):
        ResearchContract(future_data_allowed=True)


def test_contract_rejects_new_strategy_direction() -> None:
    with pytest.raises(ValueError, match="new trading direction"):
        ResearchContract(strategy_may_create_new_direction=True)
