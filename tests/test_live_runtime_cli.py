from live.live_runtime_cli import build_parser


def test_hardened_runtime_cli_is_demo_by_default():
    args = build_parser().parse_args([])
    assert args.mode == "DEMO"
    assert args.symbols == "EURUSD"
    assert args.risk == 0.0025
    assert args.interval == 5.0
    assert args.max_tick_age == 5.0
    assert args.max_spread_points == 20.0
    assert args.max_daily_drawdown == 0.01


def test_hardened_runtime_cli_exposes_only_execution_modes():
    action = next(item for item in build_parser()._actions if item.dest == "mode")
    assert action.choices == ["DEMO", "LIVE"]


def test_hardened_runtime_cli_accepts_operational_limits():
    args = build_parser().parse_args([
        "--mode", "LIVE",
        "--symbols", "EURUSD",
        "--timeframe", "1m",
        "--risk", "0.002",
        "--interval", "2.5",
        "--max-tick-age", "4",
        "--max-spread-points", "18",
        "--max-daily-drawdown", "0.008",
    ])
    assert args.mode == "LIVE"
    assert args.symbols == "EURUSD"
    assert args.timeframe == "1m"
    assert args.risk == 0.002
    assert args.interval == 2.5
    assert args.max_tick_age == 4.0
    assert args.max_spread_points == 18.0
    assert args.max_daily_drawdown == 0.008
