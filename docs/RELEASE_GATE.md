# Ariatrading Paper Release Gate

This document defines the release gate for the paper/demo runtime. A PASS is an engineering/research result only; it is not evidence of profitability and it does not authorize live-money execution.

## Required checks

1. **CI green:** Python tests, Worker tests/syntax, polyglot builds, dependency audit, secret scan, Bodyguard regression, and this release gate must pass.
2. **Hard crash recovery:** a terminated process must leave a durable checkpoint that a fresh process can inspect. Pending/unknown execution is HALT until an independent source of truth reconciles it.
3. **Backtest/realtime/paper parity:** identical historical decision windows must preserve deterministic signal identity and direction at the shared strategy boundary. Supervisor filtering is treated as a separate safety layer and may convert a directional signal to WAIT.
4. **Real historical data:** the CI gate downloads a pinned EURUSD 5-minute OHLCV sample from an external public dataset commit and validates schema, geometry, timestamps, chronological ordering, deterministic realtime replay, and paper-runtime execution.
5. **Operational console:** health, lifecycle, heartbeat, last closed bar, balance, equity, P/L, peak equity, drawdown, win rate, position, alerts, release-gate checks, equity history, events, recovery, and snapshot export must be observable.
6. **Long-term persistence:** checkpoint state is complemented by an append-only, hash-chained paper history file so the account history survives checkpoint replacement.
7. **Failure injection:** timeout-after-accept, disconnect-before-submit, rejection, partial fill, missing position, duplicate/old bar, out-of-order bar, and checkpoint corruption are explicit test cases.
8. **Security/operations:** fail-closed behavior is required for corrupted state, unresolved execution, malformed feed data, duplicate events, persistence failures, and unexpected lifecycle transitions.

## Historical data provenance

The CI fixture is pinned to a specific public Git commit rather than an unpinned moving URL. The current gate uses `getdata-finance/eurusd-5m-ohlcv-forex-historical-data` commit `665f2c90686b5a7fc5feb670ce2c3af9a3a060b8` and its `EURUSD_5m.csv` sample. The upstream repository documents the schema as `datetime, open, high, low, close, volume` and the sample as EURUSD 5-minute OHLCV data. The gate treats the downloaded file as external evidence and does not copy or modify it into the repository.

## Interpretation

- **PASS:** the tested engineering properties held for the selected fixture and code revision.
- **FAIL:** the release remains blocked from promotion beyond paper/demo.
- **No-profit inference:** a passing gate cannot establish that the strategy makes money.
- **No-live switch:** this gate intentionally has no path that sends an order to a real broker.
