# Ariatrading Version

Current version: **0.17.5**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.5 — MT5 snapshot fingerprint hardening

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics remain on one normalized three-way decision stream.
- The runnable `live/mt5_market_bridge.py` remains read-only and provides the canonical MT5 market payload contract.
- `Mt5MarketStore` now rejects non-chronological or duplicate completed candles and requires the forming candle to be newer than completed history.
- The MT5 market store now produces a deterministic SHA-256 fingerprint of the completed-candle snapshot only; changing the forming candle does not change this identity.
- `/api/signal` now requires and propagates the MT5 market fingerprint, binding strategy evaluation to the same completed-candle snapshot used by the market path.
- The legacy Pages `/api/market` compatibility function now requires a valid fingerprint contract before serving a market snapshot.
- Webaria `live-market.js` now fails closed rather than rendering a chart and strategy result when their MT5 snapshot fingerprints differ.
- A dedicated regression suite covers store fingerprinting, chronology, signal propagation, and browser fail-closed behavior.
- CI runs the new fingerprint certification suite alongside the existing MT5 E2E contract tests.
- Webaria remains MT5 single-source for chart and strategy; `/api/signal` does not fall back to a synthetic provider.
- The runtime remains PAPER/DEMO only; real-money execution is outside the supported release boundary.

## Release interpretation

A 0.17.5 PASS means the tested engineering properties held for the selected code revision and fixtures. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
