"""Run the ARIA realtime paper runtime against a signal HTTP endpoint.

Example:
  python scripts/run_paper_runtime.py --base-url http://127.0.0.1:8788/api/signal

The command is permanently PAPER mode. It only talks to the market-data/signal
HTTP endpoint and the local deterministic PaperBrokerSimulator.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from adapters.http_closed_candle_feed import HttpClosedCandleFeed
from adapters.paper_broker import PaperBrokerSimulator
from strategy.broker_contract import SymbolContract
from strategy.paper_runtime import PaperTradingRuntime
from strategy.portfolio_risk import PortfolioRiskController
from strategy.realtime import RealtimeMonitor
from strategy.risk_engine import RiskLimits, evaluate_risk


def build_runtime(base_url: str, symbol: str, timeframe: str, state_dir: Path) -> PaperTradingRuntime:
    feed = HttpClosedCandleFeed(base_url)
    monitor = RealtimeMonitor(feed, symbol, timeframe, lookback=100)
    contract = SymbolContract(
        symbol=symbol,
        digits=5,
        point=0.00001,
        volume_min=0.1,
        volume_max=100.0,
        volume_step=0.1,
    )
    broker = PaperBrokerSimulator()
    loop = __import__("strategy.paper_trading_loop", fromlist=["PaperTradingLoop"]).PaperTradingLoop(
        broker=broker,
        journal_path=state_dir / "execution.jsonl",
        symbol=symbol,
        contract=contract,
    )
    portfolio = PortfolioRiskController(initial_equity=10_000.0)
    risk_limits = RiskLimits()

    def risk_provider(evaluation):
        portfolio_decision = portfolio.evaluate()
        signal = evaluation.signal
        if not portfolio_decision.allowed:
            return portfolio_decision, evaluate_risk(
                equity=portfolio.state.equity,
                entry=signal.entry_reference or 1.0,
                stop=signal.stop_reference or 0.999,
                limits=risk_limits,
            )
        if signal.entry_reference is None or signal.stop_reference is None:
            return portfolio_decision, evaluate_risk(
                equity=portfolio.state.equity,
                entry=1.0,
                stop=0.999,
                limits=risk_limits,
            )
        trade_decision = evaluate_risk(
            equity=portfolio.state.equity,
            entry=signal.entry_reference,
            stop=signal.stop_reference,
            limits=risk_limits,
            open_positions=1 if loop.position else 0,
        )
        return portfolio_decision, trade_decision

    return PaperTradingRuntime(
        monitor=monitor,
        loop=loop,
        state_path=state_dir / "runtime.json",
        risk_provider=risk_provider,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ARIA realtime paper trading runtime")
    parser.add_argument("--base-url", required=True, help="Existing /api/signal endpoint URL")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--state-dir", default=".paper-runtime")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be > 0")

    state_dir = Path(args.state_dir)
    runtime = build_runtime(args.base_url, args.symbol, args.timeframe, state_dir)
    ready = runtime.start()
    print(f"mode={runtime.mode} status={ready.status} reason={ready.reason}")
    if ready.status != "READY":
        return 2

    try:
        while True:
            result = runtime.tick()
            print(f"status={result.status} reason={result.reason}")
            if result.status == "HALT":
                return 3
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("paper runtime stopped by operator")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
