from live.runtime_cli import build_parser


def test_stage2_runtime_cli_keeps_safe_demo_defaults():
    args = build_parser().parse_args([])
    assert args.mode == "DEMO"
    assert args.symbols == "EURUSD"
    assert args.risk == 0.0025


def test_stage2_can_be_selected_without_changing_cli_contract(monkeypatch):
    monkeypatch.setenv("ARIATRADING_ENABLE_LIVE", "I_UNDERSTAND_REAL_ORDERS")
    monkeypatch.setenv("ARIATRADING_LIVE_STAGE", "2")
    monkeypatch.setenv("ARIATRADING_LIVE_ACCOUNT", "22334455")
    monkeypatch.setenv("ARIATRADING_LIVE_SERVER", "Broker-Real")
    monkeypatch.setenv("ARIATRADING_LIVE_SYMBOLS", "EURUSD,GBPUSD")
    args = build_parser().parse_args([
        "--mode", "LIVE",
        "--symbols", "EURUSD,GBPUSD",
        "--risk", "0.005",
    ])
    assert args.mode == "LIVE"
    assert args.symbols == "EURUSD,GBPUSD"
    assert args.risk == 0.005
