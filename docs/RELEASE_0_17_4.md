# Release 0.17.4 — MT5 end-to-end contract certification

## Scope

This release adds an automated cross-language contract test for the MT5 market-data path.

## Verified path

`Python MT5 bridge-shaped payload -> Mt5MarketStore -> /api/market -> canonical /api/signal -> strategy result`

The test uses one payload for the complete chain, verifies that completed candles remain distinct from the forming candle, and checks that broker price/source identity survives the handoff.

## CI

The test workflow now generates the MT5-shaped fixture with Python and runs the JavaScript Store/strategy integration test on every relevant push and pull request. JavaScript syntax coverage includes the new E2E test.

## Failure coverage

The integration suite rejects a forming candle that is duplicated in the completed-candle set. The canonical signal path continues to fail closed for unavailable or invalid MT5 data.

## Safety boundary

This remains PAPER/DEMO only. The bridge is read-only, no broker order is placed by the E2E harness, and passing the test is engineering evidence rather than a profitability claim or authorization for real-money trading.
