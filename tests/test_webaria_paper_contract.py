from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBARIA = ROOT / "Webaria" / "index.html"
PAPER_TERMINAL = ROOT / "Webaria" / "paper-terminal.js"
PAPER_ENGINE = ROOT / "Webaria" / "paper-engine.js"
TRADING = ROOT / "Webaria" / "trading.js"


def test_webaria_has_modular_paper_trading_contract():
    html = WEBARIA.read_text(encoding="utf-8")

    required_markers = (
        "PAPER TRADING",
        'id="buy"',
        'id="sell"',
        'id="close"',
        'id="sl"',
        'id="tp"',
        'id="history"',
        'id="resetPaper"',
        "Reset Paper Account",
        "Simulation only",
        "execution NONE",
        "/paper-engine.js",
        "/paper-terminal.js",
    )

    for marker in required_markers:
        assert marker in html, f"missing Webaria paper-trading marker: {marker}"


def test_webaria_paper_trading_is_explicitly_non_broker():
    html = WEBARIA.read_text(encoding="utf-8")
    engine = PAPER_ENGINE.read_text(encoding="utf-8")
    terminal = PAPER_TERMINAL.read_text(encoding="utf-8")

    assert "never reach a broker" in html
    assert "localStorage" in terminal
    assert "webaria-paper-account-v1" in terminal
    assert "never calls a broker" in engine


def test_webaria_enforces_single_open_position_and_stop_safety():
    terminal = PAPER_TERMINAL.read_text(encoding="utf-8")
    engine = PAPER_ENGINE.read_text(encoding="utf-8")

    assert "if (state.position)" in terminal
    assert "Only one paper position is allowed at a time." in terminal
    assert "validateStops(side, entry, sl, tp)" in terminal
    assert "stop loss" in engine
    assert "take profit" in engine
    assert "barExit(position, bar)" in terminal


def test_webaria_has_signal_and_live_price_api_contracts():
    trading = TRADING.read_text(encoding="utf-8")
    terminal = PAPER_TERMINAL.read_text(encoding="utf-8")

    assert "/api/signal" in trading
    assert "/api/price" in trading
    assert "j.signal" in trading
    assert "entry_reference" in trading
    assert "stop_reference" in trading
    assert "/api/signal?" in terminal


def test_webaria_reset_cannot_discard_an_open_position():
    terminal = PAPER_TERMINAL.read_text(encoding="utf-8")

    assert "function resetPaperAccount()" in terminal
    assert "if (state.position)" in terminal
    assert "Reset rejected while a paper position is open" in terminal
    assert "state = { balance: START_BALANCE, position: null, history: [] }" in terminal
