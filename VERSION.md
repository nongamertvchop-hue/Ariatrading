# Ariatrading Version

Current version: **0.17.4**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.4 — MT5 end-to-end contract certification

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics remain on one normalized three-way decision stream.
- The runnable `live/mt5_market_bridge.py` remains read-only and provides the canonical MT5 market payload contract.
- A cross-language E2E test now takes one MT5-shaped payload from the Python bridge layer through `Mt5MarketStore` and the canonical `/api/signal` strategy adapter.
- The E2E contract verifies completed/forming candle separation, broker-source identity, price propagation, and fail-closed rejection of an invalid forming-candle relationship.
- CI generates the bridge contract fixture and runs the Python-to-Worker E2E chain on every relevant push and pull request.
- Webaria remains MT5 single-source for chart and strategy; `/api/signal` does not fall back to a synthetic provider.
- The runtime remains PAPER/DEMO only; real-money execution is outside the supported release boundary.

## Release interpretation

A 0.17.4 PASS means the tested engineering properties held for the selected code revision and fixtures. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
