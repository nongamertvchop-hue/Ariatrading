"""Bodyguard(Aria) policy unit tests."""

from bodyguard.core.policy import detect_probe, validate_method, validate_symbol, validate_timeframe


def test_symbol_ok():
    assert validate_symbol("EUR/USD").allow is True


def test_symbol_bad():
    assert validate_symbol("HACK").allow is False
    assert validate_symbol("../etc/passwd").allow is False


def test_timeframe_ok():
    assert validate_timeframe("15m").allow is True


def test_timeframe_bad():
    assert validate_timeframe("99y").allow is False


def test_method_ok():
    assert validate_method("GET").allow is True


def test_method_bad():
    assert validate_method("DELETE").allow is False


def test_probe_blocks_traversal():
    assert detect_probe("/api/signal?x=../etc/passwd").allow is False


def test_probe_blocks_script():
    assert detect_probe("/api/signal?x=<script>alert(1)</script>").allow is False


def test_probe_allows_clean():
    assert detect_probe("/api/signal?symbol=EUR/USD&timeframe=15m").allow is True
