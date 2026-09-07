# Ariatrading Version

Current version: **0.13.4**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.13.4

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure, fake-breakout sequencing, MTF context, setup scoring, risk planning, and realtime closed-candle monitoring remain connected through the existing engine.
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
- Research provenance can now be persisted and loaded atomically with schema validation.
- Feed integrity validation now runs directly at the realtime boundary, rejecting malformed OHLC, duplicate/out-of-order timestamps, non-UTC timestamps by default, and timestamps misaligned to the configured timeframe grid. It intentionally does not treat FX session/weekend gaps as automatically invalid.
- Deep-learning walk-forward research can persist a deterministic provenance artifact describing its dataset and full model/research configuration, without forcing provenance writes when the feature is unused.
- Position reconciliation now optionally tracks average entry price and enforces normalized broker symbol/volume contract consistency, while remaining backward compatible with older snapshots.
- Average-entry and broker-contract mismatches fail closed before a reconciled position can be considered safe.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.13.x — production-boundary hardening
- Complete identical-window classical ML/LSTM/Transformer comparison and strict final-OOS separation.
- Add execution-friction sensitivity reports and deterministic realtime/replay parity checks.
- Audit all research artifact persistence for atomicity, schema evolution, and corruption handling.
- Integrate reconciled average-entry/contract state into the end-to-end paper recovery assertions where applicable.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
