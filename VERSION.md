# Ariatrading Version

Current version: **0.15.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.15.1

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
- Research provenance fingerprints dataset content, ordered feature definitions, model configuration, and code version so ML/DL artifacts can be compared reproducibly and persisted atomically with schema validation.
- Feed integrity validation runs directly at the realtime boundary, rejecting malformed OHLC, duplicate/out-of-order timestamps, non-UTC timestamps by default, and timestamps misaligned to the configured timeframe grid. FX session/weekend gaps are not automatically treated as invalid.
- Deep-learning walk-forward research can persist deterministic provenance artifacts without forcing provenance writes when the feature is unused.
- Position reconciliation optionally tracks average entry price and enforces normalized broker symbol/volume contract consistency; mismatches fail closed.
- MT5 integration remains read-only; no order execution is implemented.
- Webaria includes a realtime Signal Advisor backed by the Worker market-data API and a browser-safe Paper Risk Engine.
- A dedicated MTF Signal Advisor evaluates 1D -> 4H -> 1H -> 15M using the existing `/api/signal` outputs. Higher timeframes filter an existing 15M setup and cannot create a third strategy.
- Worker market-data traffic passes through a lightweight cache gateway with short-lived fresh caching and stale fallback for temporary provider/quota/network errors. The gateway does not execute orders or expose secrets.
- Signal journal events now have deterministic IDs derived from symbol, timeframe, closed-bar decision time and action, enabling duplicate-safe research snapshots without relying on evaluation wall-clock time.
- `live/paper_runtime.py` provides the automatic closed-candle paper runtime. It continuously drives the existing realtime monitor and paper-session lifecycle, exposes operational snapshots, supports bounded runs for tests, and fails closed on unexpected runtime errors.
- The runtime explicitly rejects DEMO mode until a real MT5 execution adapter exists, preventing accidental promotion from paper simulation to broker execution.
- Runtime checkpoints use atomic JSON persistence and restore the session, paper account, open position, pending signal, last processed candle, and journal state.
- Cross-component reconciliation now validates paper position, journal OPEN/CLOSE lifecycle, account counters, pending signal, and checkpoint timeline invariants before restart can resume.
- Automation runtime behavior, persistence, reconciliation, and signal-event deduplication are covered by dedicated tests.

## Next milestones

### 0.15.x — automation validation and demo boundary
- Add historical signal replay to the automatic runtime using the same realtime replay semantics as Python.
- Add outcome labeling for paper signals only after the next completed bars are known, without changing the live signal itself.
- Compare MTF filtered vs unfiltered paper signals on identical chronological windows.
- Add signal-quality reports by timeframe, regime, breakout state, and setup score bucket.
- Add a broker-neutral execution interface and a separate MT5 demo adapter only after the paper/runtime contracts remain green.
- Continue auditing execution-friction sensitivity and realtime/replay parity.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
