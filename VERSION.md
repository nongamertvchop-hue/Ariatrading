# Ariatrading Version

Current version: **0.14.4**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.14.4

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
- Research provenance fingerprints dataset content, ordered feature definitions, model configuration, and code version so ML/DL artifacts can be compared reproducibly, with atomic persistence and schema validation.
- Feed integrity validation runs directly at the realtime boundary, rejecting malformed OHLC, duplicate/out-of-order timestamps, non-UTC timestamps by default, and timestamps misaligned to the configured timeframe grid. It intentionally does not treat FX session/weekend gaps as automatically invalid.
- Deep-learning walk-forward research can persist a deterministic provenance artifact describing its dataset and full model/research configuration, without forcing provenance writes when the feature is unused.
- Position reconciliation optionally tracks average entry price and enforces normalized broker symbol/volume contract consistency, while remaining backward compatible with older snapshots.
- Average-entry and broker-contract mismatches fail closed before a reconciled position can be considered safe.
- MT5 integration remains read-only; no order execution is implemented.
- Webaria includes a realtime Signal Advisor backed by the Worker market-data API and a browser-safe Paper Risk Engine.
- A dedicated MTF Signal Advisor evaluates 1D -> 4H -> 1H -> 15M using the existing `/api/signal` outputs. Higher timeframes filter an existing 15M setup and cannot create a third strategy.
- The MTF Advisor records signal snapshots locally in the browser for research/journal review; the journal is not a broker execution log and is not shared between devices.
- MTF and Webaria paper-engine page contracts are covered by automated tests.
- Worker market-data traffic passes through a lightweight gateway that reduces duplicate upstream requests with short-lived fresh caching and serves recent successful snapshots as stale fallback during temporary provider/quota/network errors.
- The Worker `/api/signal` path now uses a dedicated parity implementation that mirrors the Python realtime engine's candle pressure, confirmed zones, zone-center semantics, fake-breakout classification, sequence evaluation, structure bias, all-zone candidate selection, scoring, forecast context, realtime supervisor gate, and nearest-zone semantics.
- Worker realtime input now has an explicit feed guard for OHLC geometry, chronological ordering, timeframe-grid alignment, stale/future data, and per-symbol/timeframe duplicate suppression.
- Worker parity contracts are covered by a Node test suite in addition to Python tests and Worker syntax checks.
- Signal events now have deterministic `sig_...` identities shared by the Python and Worker canonical payload contract, with browser journal deduplication using the event identity when available.
- Realtime event timestamps are normalized to UTC `Z` form before event hashing so equivalent timezone-aware Python timestamps do not create a different research identity from Worker output.
- Historical realtime replay can now attach causal paper-signal outcomes to each replayed event without changing the original signal decision.
- Outcome labeling is research-only and supports `WIN`, `LOSS`, `TIMEOUT`, `AMBIGUOUS`, and `INVALID`; same-candle stop/target conflicts remain explicitly ambiguous because OHLC does not encode intrabar order.

## Next milestones

### 0.14.x — signal validation and paper research
- Add historical outcome display to the Webaria Advisor using the same event IDs and replay semantics as Python.
- Compare MTF filtered vs unfiltered paper signals on identical chronological windows.
- Add signal-quality reports by timeframe, regime, breakout state, and setup score bucket.
- Continue auditing execution-friction sensitivity and realtime/replay parity.
- Replace duplicated Worker/Python strategy code with a generated/shared parity contract once the cross-runtime fixtures are complete.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
