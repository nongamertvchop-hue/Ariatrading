from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBARIA = ROOT / "Webaria" / "index.html"


def test_webaria_has_paper_trading_lifecycle_controls():
    html = WEBARIA.read_text(encoding="utf-8")

    required_markers = (
        "Paper Trading",
        'id="buy"',
        'id="sell"',
        'id="close"',
        'id="sl"',
        'id="tp"',
        'id="history"',
        "stop loss",
        "take profit",
        "Reset Paper Account",
    )

    for marker in required_markers:
        assert marker in html, f"missing Webaria paper-trading marker: {marker}"


def test_webaria_paper_trading_is_explicitly_non_broker():
    html = WEBARIA.read_text(encoding="utf-8")

    assert "never reach a broker" in html
    assert "localStorage" in html
    assert "webaria-paper-v2" in html


def test_webaria_enforces_single_open_position_and_stop_safety():
    html = WEBARIA.read_text(encoding="utf-8")

    assert "if(!Number.isFinite(price)||state.paper.position)return" in html
    assert "validStops(side,price,sl,tp)" in html
    assert "stop loss" in html
    assert "take profit" in html


def test_webaria_has_signal_and_live_price_api_contracts():
    html = WEBARIA.read_text(encoding="utf-8")

    assert "/api/signal" in html
    assert "/api/price" in html
    assert "payload.signal" in html
    assert "entry_reference" in html
    assert "stop_reference" in html
