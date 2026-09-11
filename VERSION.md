# Ariatrading Version

Current version: **0.17.3**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.3 — Webaria MT5 single-source runtime

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics remain on one normalized three-way decision stream.
- MT5 epoch-second and epoch-millisecond candle timestamps are accepted by the realtime feed guard.
- The `/api/strategy` MT5 path remains guarded before strategy evaluation and only advances its duplicate cursor after accepted evaluation.
- The runnable `live/mt5_market_bridge.py` provides read-only MT5 market data, separates completed/forming candles, exposes bid/ask, authenticates requests, and never calls `order_send()` or `order_check()`.
- Webaria `/api/market` and `/api/signal` now share the same MT5 market source; `/api/signal` fails closed rather than switching to another provider.
- Browser strategy evaluation uses completed MT5 candles; the forming candle is display context only.
- The Webaria live terminal reports `MT5 LIVE · STRATEGY LIVE` only when both market and strategy paths accept the MT5 feed.
- A dedicated regression test verifies MT5-backed signal evaluation and fail-closed behavior.
- The runtime remains PAPER/DEMO only; real-money execution is outside the supported release boundary.

## Release interpretation

A 0.17.3 PASS means the tested engineering properties held for the selected code revision and fixtures. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
