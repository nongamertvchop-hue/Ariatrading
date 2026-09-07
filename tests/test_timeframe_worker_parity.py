from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PYTHON_CONFIG = ROOT / "strategy" / "timeframe.py"
WORKER = ROOT / "worker" / "index.js"

EXPECTED_TIMEFRAMES = ("1m", "5m", "15m", "30m", "1h", "4h", "1D")


def _extract_python_multipliers(text: str) -> dict[str, float]:
    pattern = re.compile(
        r'"(?P<tf>1m|5m|15m|30m|1h|4h|1D)"\s*:\s*TimeframeConfig\('
        r'"(?:1m|5m|15m|30m|1h|4h|1D)"\s*,\s*30\s*,\s*(?P<value>[0-9]+(?:\.[0-9]+)?)\s*,'
    )
    return {match.group("tf"): float(match.group("value")) for match in pattern.finditer(text)}


def _extract_worker_multipliers(text: str) -> dict[str, float]:
    pattern = re.compile(
        r'"(?P<tf>1m|5m|15m|30m|1h|4h|1D)"\s*:\s*\{[^\n]*?'
        r'rangeMultiplier:\s*(?P<value>[0-9]+(?:\.[0-9]+)?)\s*,'
    )
    return {match.group("tf"): float(match.group("value")) for match in pattern.finditer(text)}


def test_worker_range_multiplier_matches_python_timeframe_source():
    python_values = _extract_python_multipliers(PYTHON_CONFIG.read_text(encoding="utf-8"))
    worker_values = _extract_worker_multipliers(WORKER.read_text(encoding="utf-8"))

    assert tuple(python_values) == EXPECTED_TIMEFRAMES
    assert tuple(worker_values) == EXPECTED_TIMEFRAMES
    assert worker_values == python_values
