"""Long-duration paper shadow run over pinned real historical market data."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .historical_data import load_ohlcv_csv
from .parity_certification import certify_three_way_parity


@dataclass(frozen=True)
class HistoricalShadowReport:
    passed: bool
    bars: int
    compared: int
    decision_fingerprint: str
    paper_trades: int
    paper_balance: float
    paper_equity: float
    paper_drawdown: float
    repeatable: bool

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "bars": self.bars,
            "compared": self.compared,
            "decision_fingerprint": self.decision_fingerprint,
            "paper_trades": self.paper_trades,
            "paper_balance": self.paper_balance,
            "paper_equity": self.paper_equity,
            "paper_drawdown": self.paper_drawdown,
            "repeatable": self.repeatable,
        }


def _run(csv_path: str | Path, checkpoint_path: Path, *, max_rows: int) -> HistoricalShadowReport:
    candles = load_ohlcv_csv(csv_path, max_rows=max_rows)
    certificate = certify_three_way_parity(
        candles=candles,
        symbol="EURUSD",
        timeframe="5m",
        checkpoint_path=checkpoint_path,
        start_index=100,
    )
    return HistoricalShadowReport(
        passed=certificate.passed,
        bars=len(candles),
        compared=certificate.compared,
        decision_fingerprint=certificate.realtime_fingerprint,
        paper_trades=certificate.paper_trades,
        paper_balance=certificate.paper_balance,
        paper_equity=certificate.paper_equity,
        paper_drawdown=certificate.paper_drawdown,
        repeatable=True,
    )


def run_long_shadow(csv_path: str | Path, *, checkpoint_dir: str | Path, max_rows: int = 10_000) -> HistoricalShadowReport:
    """Run the full real-history paper shadow twice and require identical evidence."""
    if max_rows < 1_000:
        raise ValueError("long shadow requires at least 1,000 historical bars")
    root = Path(checkpoint_dir)
    root.mkdir(parents=True, exist_ok=True)
    first = _run(csv_path, root / "shadow-a.json", max_rows=max_rows)
    second = _run(csv_path, root / "shadow-b.json", max_rows=max_rows)
    repeatable = (
        first.passed == second.passed
        and first.bars == second.bars
        and first.compared == second.compared
        and first.decision_fingerprint == second.decision_fingerprint
        and first.paper_trades == second.paper_trades
        and first.paper_balance == second.paper_balance
        and first.paper_equity == second.paper_equity
        and first.paper_drawdown == second.paper_drawdown
    )
    return HistoricalShadowReport(
        passed=first.passed and second.passed and repeatable,
        bars=first.bars,
        compared=first.compared,
        decision_fingerprint=first.decision_fingerprint,
        paper_trades=first.paper_trades,
        paper_balance=first.paper_balance,
        paper_equity=first.paper_equity,
        paper_drawdown=first.paper_drawdown,
        repeatable=repeatable,
    )


__all__ = ["HistoricalShadowReport", "run_long_shadow"]
