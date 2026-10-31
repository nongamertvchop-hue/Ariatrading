from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_demo_runtime_page_uses_read_only_mt5_status_endpoint() -> None:
    source = (ROOT / "Webaria" / "demo-runtime.html").read_text(encoding="utf-8")
    assert "/api/mt5/status" in source
    assert "/api/order" not in source
    assert "/api/execute" not in source
    assert "/api/trade" not in source
    assert "read-only" in source.lower()
    assert "setInterval(refresh,3000)" in source


def test_demo_bot_entrypoint_publishes_runtime_status() -> None:
    source = (ROOT / "scripts" / "run_demo_bot.py").read_text(encoding="utf-8")
    assert "RuntimeStatusStore" in source
    assert 'status = RuntimeStatusStore(args.status_path)' in source
    assert "status=status" in source
