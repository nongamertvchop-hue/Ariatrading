# Ariatrading Version

Current version: **0.13.2**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.13.2

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure, fake-breakout sequencing, MTF context, setup scoring, risk planning, and realtime closed-candle monitoring remain connected through the existing engine.
- Timestamp-aligned MTF context excludes higher-timeframe candles that have not fully closed at the entry timestamp.
- Sequential backtests support bounded evaluation windows so research can isolate out-of-sample periods without allowing exits to cross the test boundary.
- Backtest entry timing is explicit: the legacy signal-reference assumption remains available, while `next_bar_open` matches the paper-session lifecycle.
- Historical execution simulation models spread, commission, slippage, bar-based latency, session boundaries and price precision without placing orders.
- ML research includes chronological OOS evaluation, feature drift, behavior, health/calibration, stability, evidence readiness, and LSTM/Transformer challenger comparisons.
- Optional deep-learning research remains causal and isolated from broker execution.
- The final system readiness gate combines strategy protection, realtime data quality, portfolio risk, trade risk, broker contract validation, position reconciliation, execution recovery, and optional ML evidence into one fail-closed pre-execution contract.
- The deterministic paper broker and end-to-end paper recovery coordinator cover full/partial fills, rejection, disconnect/timeout ambiguity, idempotency, durable multi-order state, audit-chain verification, and restart recovery.
- Portfolio daily-loss accounting combines independently recorded realized loss with session-equity loss using the maximum rather than summing both sources, preventing double counting while preserving a fail-closed limit.
- Broker-symbol contract validation now provides an explicit execution-boundary check for symbol identity, price precision, and volume min/max/step constraints.
- Research provenance now fingerprints dataset content, ordered feature definitions, model configuration, and code version so ML/DL artifacts can be compared reproducibly.
- Feed integrity validation now rejects malformed OHLC, duplicate/out-of-order timestamps, non-UTC timestamps by default, and timestamps misaligned to the configured timeframe grid. It intentionally does not treat FX session/weekend gaps as automatically invalid.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.13.x — production-boundary hardening
- Integrate feed-integrity validation directly into the realtime feed boundary without breaking legitimate session gaps.
- Persist research provenance alongside walk-forward and deep-learning artifacts.
- Compare classical ML, LSTM and Transformer only on identical untouched OOS windows; never select a winner using the final OOS window.
- Add execution-friction sensitivity reports and historical replay parity checks.
- Expand paper-position reconciliation to include explicit average-entry/position-contract checks.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
