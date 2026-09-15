from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_demo_bot.py"


def test_demo_entrypoint_exists_and_uses_demo_mode() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'validate_account_mode(executor.mt5, "DEMO")' in source
    assert 'mode="DEMO"' in source
    assert 'choices=["LIVE"]' not in source


def test_demo_entrypoint_does_not_accept_runtime_mode_override() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--mode"' not in source
