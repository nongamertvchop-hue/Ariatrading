from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "Webaria" / "signal-advisor.html"


def test_signal_advisor_page_has_real_market_signal_contract():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        "/api/signal",
        "/paper-engine.js",
        "LONG",
        "SHORT",
        "WAIT",
        "structure_bias",
        "entry_reference",
        "stop_reference",
        "breakout_state",
        "score",
    ):
        assert marker in html


def test_signal_advisor_is_paper_only():
    html = PAGE.read_text(encoding="utf-8")
    assert "Paper Trading" in html
    assert "ไม่มีการส่งคำสั่งไป broker" in html
