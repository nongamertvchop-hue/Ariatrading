import pytest

from live.runner import ForexLiveOrchestrator


def _arm(monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "1")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "12345")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", "EURUSD")


def test_live_orchestrator_rejects_multiple_symbols(monkeypatch):
    _arm(monkeypatch)
    with pytest.raises(RuntimeError, match="symbol allowlist mismatch"):
        ForexLiveOrchestrator(
            symbols=["EURUSD", "GBPUSD"],
            mode="LIVE",
            risk_per_trade=0.0025,
        )


def test_live_orchestrator_rejects_risk_above_stage1_cap(monkeypatch):
    _arm(monkeypatch)
    with pytest.raises(RuntimeError, match="risk exceeds policy"):
        ForexLiveOrchestrator(
            symbols=["EURUSD"],
            mode="LIVE",
            risk_per_trade=0.005,
        )
