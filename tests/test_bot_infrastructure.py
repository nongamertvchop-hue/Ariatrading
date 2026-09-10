from __future__ import annotations

from bot.config import BotConfig
from bot.orders import ExitPair, OrderIntent, OrderType
from bot.rate_limit import TokenBucket
from bot.storage import SQLiteStore


def test_config_defaults_are_fail_closed(monkeypatch):
    monkeypatch.setenv("BOT_MODE", "paper")
    monkeypatch.delenv("ALLOW_LIVE", raising=False)
    config = BotConfig.from_env()
    assert config.mode == "paper"
    assert config.allow_live is False


def test_live_mode_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("BOT_MODE", "live")
    monkeypatch.delenv("ALLOW_LIVE", raising=False)
    try:
        BotConfig.from_env()
    except RuntimeError as exc:
        assert "fail-closed" in str(exc)
    else:
        raise AssertionError("LIVE mode must be blocked by default")


def test_order_intent_validates_long_exit_geometry():
    intent = OrderIntent("abc", "EURUSD", "LONG", OrderType.MARKET, 0.1, 1.1000, ExitPair(1.0950, 1.1100))
    intent.validate()
    assert intent.oco_group == "oco:abc"


def test_rate_limiter_rejects_burst_after_capacity():
    bucket = TokenBucket(rate=1, capacity=2)
    assert bucket.allow()
    assert bucket.allow()
    assert not bucket.allow()


def test_sqlite_store_round_trip(tmp_path):
    store = SQLiteStore(str(tmp_path / "runtime.db"))
    event_id = store.append_event("TEST", {"ok": True})
    store.set_state("heartbeat", {"n": 1})
    assert event_id == 1
    assert store.get_state("heartbeat") == {"n": 1}
    assert store.recent_events(1)[0]["payload"] == {"ok": True}
    store.close()
