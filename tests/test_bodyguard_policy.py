"""Bodyguard(Aria) policy and sanitization unit tests (v0.05.0)."""

from bodyguard.core.policy import (
    detect_probe,
    detect_prototype_pollution,
    normalize_and_detect_evasion,
    validate_cors_origin,
    validate_execution_isolation,
    validate_method,
    validate_symbol,
    validate_timeframe,
)
from bodyguard.core.sanitize import scrub_mapping, scrub_text


# --- Core Policy Tests (R3, R4) ---

def test_symbol_ok():
    assert validate_symbol("EUR/USD").allow is True
    assert validate_symbol("GBP/JPY").allow is True


def test_symbol_bad():
    assert validate_symbol("HACK").allow is False
    assert validate_symbol("../etc/passwd").allow is False
    assert validate_symbol("").allow is False


def test_timeframe_ok():
    assert validate_timeframe("15m").allow is True
    assert validate_timeframe("1h").allow is True
    assert validate_timeframe("1D").allow is True


def test_timeframe_bad():
    assert validate_timeframe("99y").allow is False
    assert validate_timeframe("").allow is False


def test_method_ok():
    assert validate_method("GET").allow is True
    assert validate_method("HEAD").allow is True
    assert validate_method("OPTIONS").allow is True


def test_method_bad():
    assert validate_method("DELETE").allow is False
    assert validate_method("POST").allow is False


# --- Probe & Evasion Detection (R12) ---

def test_probe_blocks_traversal():
    assert detect_probe("/api/signal?x=../etc/passwd").allow is False
    assert detect_probe("/api/signal?x=%2e%2e/windows/win.ini").allow is False


def test_probe_blocks_script():
    assert detect_probe("/api/signal?x=<script>alert(1)</script>").allow is False
    assert detect_probe("/api/signal?x=javascript:eval(1)").allow is False


def test_probe_blocks_double_encoding_evasion():
    # %252e%252e decodes to %2e%2e which decodes to ..
    res = normalize_and_detect_evasion("/api/price?x=%252e%252e/secret")
    assert res.allow is False
    assert "double_encoding" in res.reason


def test_probe_blocks_null_byte():
    res = normalize_and_detect_evasion("/api/signal?x=safe%00evil")
    assert res.allow is False
    assert "null_byte" in res.reason


def test_probe_allows_clean():
    assert detect_probe("/api/signal?symbol=EUR/USD&timeframe=15m").allow is True


# --- Prototype Pollution (R15) ---

def test_prototype_pollution_blocked():
    payload1 = {"__proto__": {"polluted": True}}
    res1 = detect_prototype_pollution(payload1)
    assert res1.allow is False
    assert "prototype pollution" in res1.reason

    payload2 = {"user": {"constructor": {"prototype": {"admin": True}}}}
    res2 = detect_prototype_pollution(payload2)
    assert res2.allow is False
    assert "prototype pollution" in res2.reason


def test_prototype_pollution_clean():
    payload = {"symbol": "EUR/USD", "timeframe": "15m", "candles": [{"open": 1.1, "close": 1.2}]}
    res = detect_prototype_pollution(payload)
    assert res.allow is True


def test_payload_depth_limit():
    # Construct 7 levels deep (exceeds max_depth=5)
    deep = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
    res = detect_prototype_pollution(deep, max_depth=5)
    assert res.allow is False
    assert "max depth" in res.reason


# --- Execution Boundary Isolation (R16) ---

def test_execution_isolation_blocks_trading():
    assert validate_execution_isolation("/api/order?symbol=EURUSD").allow is False
    assert validate_execution_isolation("/api/execute").allow is False
    assert validate_execution_isolation("/api/trade/new").allow is False
    assert validate_execution_isolation("/api/buy").allow is False
    assert validate_execution_isolation("/api/mt5/send").allow is False


def test_execution_isolation_allows_public_research():
    assert validate_execution_isolation("/api/signal?symbol=EUR/USD").allow is True
    assert validate_execution_isolation("/api/price?symbol=EUR/USD").allow is True
    assert validate_execution_isolation("/api/bodyguard/status").allow is True


# --- CORS Origin Protection (R17) ---

def test_cors_origin_allowed():
    assert validate_cors_origin("https://webaria.pages.dev").allow is True
    assert validate_cors_origin("http://localhost:8787").allow is True
    assert validate_cors_origin("").allow is True  # Same-origin allowed


def test_cors_origin_rejected():
    assert validate_cors_origin("https://malicious-site.com").allow is False
    assert validate_cors_origin("http://evil-attacker.org").allow is False


# --- Sanitization & Secret Scrubbing (R1, R7) ---

def test_scrub_telegram_token():
    text = "Starting bot with token 123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789"
    scrubbed = scrub_text(text)
    assert "[REDACTED_TELEGRAM_TOKEN]" in scrubbed
    assert "123456789:ABC" not in scrubbed


def test_scrub_jwt():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGz_W_example"
    text = f"Bearer {jwt}"
    scrubbed = scrub_text(text)
    assert "[REDACTED_JWT]" in scrubbed
    assert jwt not in scrubbed


def test_scrub_mt5_credentials_in_mapping():
    data = {
        "user": "trader",
        "mt5_password": "SuperSecretPassword123!",
        "telegram_bot_token": "987654321:XYZ-bot-token-abc1234567890123456",
        "nested": {
            "api_key": "live-api-key-998877",
            "safe_value": 42,
        },
    }
    scrubbed = scrub_mapping(data)
    assert scrubbed["mt5_password"] == "[REDACTED]"
    assert scrubbed["telegram_bot_token"] == "[REDACTED]"
    assert scrubbed["nested"]["api_key"] == "[REDACTED]"
    assert scrubbed["nested"]["safe_value"] == 42
