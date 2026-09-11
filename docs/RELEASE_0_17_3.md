# Release 0.17.3 — Webaria MT5 single-source runtime

## Scope

This release makes MT5 the single market-data source for the Webaria chart and realtime strategy signal path.

## Runtime path

`MT5 terminal -> read-only bridge -> /api/mt5/ingest -> Mt5MarketStore -> /api/market + /api/signal -> Webaria`

The strategy endpoint no longer substitutes another market provider when MT5 data is unavailable. It validates the same completed-candle stream through the realtime feed guard before evaluation.

## Browser behavior

The live terminal reads `/api/market`, evaluates `/api/signal`, and renders `MT5 LIVE · STRATEGY LIVE` only when the broker-backed market and strategy responses are both accepted. The forming candle is display context and is not used as a strategy candle.

## Verification

- Added `tests/test_worker_mt5_single_source.mjs` to verify MT5-backed signal evaluation and fail-closed behavior.
- CI worker tests and syntax checks now include the new regression test and the live-market browser module.

## Safety boundary

This release remains PAPER/DEMO only. The MT5 bridge is read-only and does not call broker order execution functions. A successful data-path test is not a profitability claim and does not authorize real-money trading.
