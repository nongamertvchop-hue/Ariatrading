import pytest

from bot.config import BotConfig


def _arm(monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "1")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "12345")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", "EURUSD")


def test_bot_live_mode_is_fail_closed_without_stage1(monkeypatch):
    monkeypatch.setenv("BOT_MODE", "live")
    monkeypatch.setenv("DEFAULT_SYMBOLS", "EURUSD")
    monkeypatch.setenv("DEFAULT_RISK_PER_TRADE", "0.0025")
    monkeypatch.delenv("ARIATRADING_LIVE_STAGE", raising=False)
    with pytest.raises(RuntimeError, match="LIVE production stage is not armed"):
        BotConfig.from_env()


def test_bot_live_mode_requires_stage1_symbol_and_risk(monkeypatch):
    _arm(monkeypatch)
    monkeypatch.setenv("BOT_MODE", "live")
    monkeypatch.setenv("DEFAULT_SYMBOLS", "EURUSD")
    monkeypatch.setenv("DEFAULT_RISK_PER_TRADE", "0.0025")
    config = BotConfig.from_env()
    assert config.mode == "live"
    assert config.symbols == ("EURUSD",)

    monkeypatch.setenv("DEFAULT_RISK_PER_TRADE", "0.005")
    with pytest.raises(RuntimeError, match="risk exceeds policy"):
        BotConfig.from_env()
