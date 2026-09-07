from datetime import datetime, timedelta, timezone

from strategy.research_control import ResearchConfig
from strategy.research_runner import run_controlled_research


def make_candles(n=50):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = []
    price = 1.1000
    for i in range(n):
        move = 0.0002 if i % 2 == 0 else -0.0001
        data.append(
            {
                "time": start + timedelta(minutes=i),
                "open": price,
                "high": price + 0.0010,
                "low": price - 0.0010,
                "close": price + move,
            }
        )
        price += move
    return data


def test_controlled_research_binds_metadata_to_walk_forward():
    candles = make_candles()
    config = ResearchConfig(
        symbol="EURUSD",
        timeframe="15m",
        history_bars=20,
        test_bars=10,
        step_bars=10,
    )

    result = run_controlled_research(candles, config)

    assert result.control.config == config
    assert result.control.config_sha256
    assert result.control.dataset.candle_count == len(candles)
    assert result.control.dataset.sha256
    assert result.walk_forward.timeframe == config.timeframe
    assert result.walk_forward.history_bars == config.history_bars
    assert result.walk_forward.test_bars == config.test_bars
    assert result.walk_forward.step_bars == config.step_bars


def test_controlled_research_is_deterministic_for_same_inputs():
    candles = make_candles()
    config = ResearchConfig("EURUSD", "15m", 20, 10, 10)

    first = run_controlled_research(candles, config)
    second = run_controlled_research(candles, config)

    assert first == second


def test_dataset_change_changes_control_fingerprint():
    candles = make_candles()
    config = ResearchConfig("EURUSD", "15m", 20, 10, 10)
    first = run_controlled_research(candles, config)

    changed = make_candles()
    changed[-1]["close"] += 0.0001
    second = run_controlled_research(changed, config)

    assert first.control.config_sha256 == second.control.config_sha256
    assert first.control.dataset.sha256 != second.control.dataset.sha256
