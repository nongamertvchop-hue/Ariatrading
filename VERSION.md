# Ariatrading Version

Current version: **0.17.6**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.6 — MT5 canonical symbol contract

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics remain on one normalized three-way decision stream.
- The runnable `live/mt5_market_bridge.py` remains read-only and provides the canonical MT5 market payload contract.
- The MT5 bridge keeps the native terminal symbol (for example `EURUSD`) for broker queries while emitting the canonical API symbol (`EUR/USD`) required by the Worker market contract.
- Python and Worker use the same completed-candle fingerprint byte representation, including normalized FX symbol identity and 12-decimal OHLC formatting.
- `Mt5MarketStore` rejects non-chronological or duplicate completed candles and requires the forming candle to be newer than completed history.
- The market store and bridge expose a deterministic SHA-256 fingerprint of the completed-candle snapshot only.
- `/api/signal` strictly requires and propagates a valid 64-character hexadecimal MT5 market fingerprint.
- The Pages `/api/market` compatibility path accepts the canonical MT5 timestamp payload (`time`), normalizes it to the browser-facing ISO `datetime`, and validates forming-candle ordering.
- Webaria fails closed rather than rendering a chart and strategy result when their MT5 snapshot fingerprints differ.
- Regression coverage verifies canonical symbol normalization, fingerprint generation, cross-language fingerprint parity, mixed-snapshot rejection, and MT5 timestamp normalization.
- The runtime remains PAPER/DEMO only; real-money execution is outside the supported release boundary.

## Release interpretation

A 0.17.6 PASS means the tested engineering properties held for the selected code revision and fixtures. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
