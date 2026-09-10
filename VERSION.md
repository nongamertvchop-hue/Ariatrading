# Ariatrading Version

Current version: **0.15.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.15.0

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
- Broker-symbol contract validation provides an explicit execution-boundary check for symbol identity, price precision, and volume min/max/step constraints.
- Research provenance fingerprints dataset content, ordered feature definitions, model configuration, and code version so ML/DL artifacts can be compared reproducibly, with atomic persistence and schema validation.
- Feed integrity validation runs directly at the realtime boundary, rejecting malformed OHLC, duplicate/out-of-order timestamps, non-UTC timestamps by default, and timestamps misaligned to the configured timeframe grid.
- Position reconciliation optionally tracks average entry price and enforces normalized broker symbol/volume contract consistency, while remaining backward compatible with older snapshots.
- MT5 integration remains read-only; no real broker execution is implemented.
- Webaria includes a realtime Signal Advisor backed by the Worker market-data API and a browser-safe Paper Risk Engine.
- The MTF Advisor evaluates 1D -> 4H -> 1H -> 15M using existing signal outputs and cannot create a third strategy.
- Worker realtime input has an explicit feed guard for OHLC geometry, chronological ordering, timeframe-grid alignment, stale/future data, and duplicate suppression.
- Worker parity contracts are covered by Node tests in addition to Python tests and Worker syntax checks.
- Signal events use deterministic `sig_...` identities shared by Python and Worker canonical payload semantics.
- Historical realtime replay can attach causal paper-signal outcomes without changing the original signal decision.
- **Paper Runtime 0.15.0:** crash/restart recovery now has a dedicated atomic checkpoint format, unresolved pending execution remains fail-closed after restart, and corrupted checkpoint state is never silently reset.
- **Paper Accounting 0.15.0:** deterministic realized P/L, unrealized P/L, equity, peak equity, drawdown, drawdown percentage, trade count, win/loss statistics, and checkpoint validation are first-class runtime state.
- **Continuous Paper Runtime 0.15.0:** completed candles are processed once in timestamp order, paper positions are marked to market, stop/target exits are deterministic at bar resolution, and runtime state persists across restarts.
- **Paper Dashboard 0.15.0:** Webaria now exposes balance, equity, realized/unrealized P/L, peak equity, drawdown, win rate, checkpoint status, heartbeat, position, failure mode, event stream, equity curve, snapshot export, recovery, and a deterministic 10,000-bar replay control.
- **Soak/Fault Validation 0.15.0:** deterministic 10,000-bar replay and explicit timeout, disconnect, rejection, partial-fill, disappearance, duplicate-bar, out-of-order-bar, and checkpoint-corruption scenarios are covered by automated tests/documentation.
- **Operational review 0.15.0:** the final paper/demo security checklist documents safety boundaries, recovery behavior, failure expectations, replay criteria, and release interpretation.

## Next milestones

### 0.15.x — paper validation only
- Run the full GitHub Actions matrix and retain failures as regression evidence.
- Expand deterministic datasets with recorded real-market historical samples while preserving closed-candle and causal boundaries.
- Compare paper-runtime results against existing backtest/replay outcomes on identical chronological windows.
- Continue hardening observability and operational diagnostics without introducing live broker execution.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
