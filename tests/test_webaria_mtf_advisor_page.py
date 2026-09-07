from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "Webaria" / "mtf-advisor.html"


def test_mtf_advisor_page_has_supported_timeframe_matrix_and_real_signal_api():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        "1D",
        "4h",
        "1h",
        "15m",
        "/api/signal?",
        "Promise.all(TFS.map(fetchTf))",
        "WebariaPaperEngine.evaluateRisk",
    ):
        assert marker in html, f"missing MTF advisor marker: {marker}"


def test_mtf_advisor_page_is_filter_not_new_strategy():
    html = PAGE.read_text(encoding="utf-8")
    assert "15M ต้องเป็น LONG และ HTF ต้องไม่คัดค้าน" in html
    assert "15M ต้องเป็น SHORT และ HTF ต้องไม่คัดค้าน" in html
    assert "MTF alignment เป็นตัวกรองของ setup เดิม ไม่ใช่ setup ใหม่" in html


def test_mtf_advisor_page_is_simulation_only_and_local_journaled():
    html = PAGE.read_text(encoding="utf-8")
    for marker in (
        "Paper Risk Planner",
        "localStorage",
        "aria-signal-journal-v1",
        "ไม่ส่งคำสั่งไป broker",
        "ข้อมูลตลาดเป็นข้อมูลจริงสำหรับการวิจัย/ทดลองเท่านั้น",
    ):
        assert marker in html, f"missing simulation-only marker: {marker}"
