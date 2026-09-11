# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.17.5**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.
- No unrelated entry patterns are added. Context layers can filter, score, or validate these two setups, but cannot create a third setup.

## Architecture

The project is layered so every stage can be used together without duplicating strategy rules:

1. **Market structure** — confirmed swing highs/lows are labeled HH, HL, LH and LL, producing a structural bias.
2. **Zone intelligence** — repeated confirmed swings form support/resistance zones with independent, time-separated reactions and recent-break invalidation.
3. **Candle intelligence** — completed candles provide descriptive buying/selling pressure and reject non-finite OHLC values.
4. **Sequence engine** — APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM.
5. **Fake-breakout engine** — fake breaks enter the explicit reclaim path; true breaks block the setup.
6. **Multi-timeframe context** — higher/entry structure can filter and score an existing setup. Timestamp alignment prevents higher-timeframe look-ahead.
7. **Setup scoring** — transparent 0-100 heuristic quality score; never treated as win probability.
8. **Risk/backtest** — hypothetical SL/TP planning and sequential historical simulation.
9. **Execution simulation** — optional spread, commission, slippage, latency, session and precision effects, isolated from strategy decisions.
10. **Research validation** — chronological splits, R-based metrics, profit factor, drawdown and bootstrap expectancy uncertainty.
11. **Walk-forward validation** — expanding-history, rolling out-of-sample windows with hard test boundaries.
12. **ML meta-filter research** — chronological ML filtering of existing LONG/SHORT signals only.
13. **ML diagnostics** — feature drift, fold-level behavior, model health/calibration, permutation stability, and evidence consistency checks.
14. **Deep-learning challengers** — optional causal LSTM and Transformer sequence models that score existing signals but cannot create direction.
15. **Deep-learning walk-forward** — fold-by-fold expanding OOS evaluation for both LSTM and Transformer using the same signal/label chronology as classical ML.
16. **ML evidence gate** — explicit readiness policy that can require regime, stability, robustness, behavior, drift, and both deep-learning challengers.
17. **Research provenance** — deterministic dataset, feature-order, model-config, and code-version fingerprints for reproducible ML/DL experiments, with atomic persistence.
18. **Realtime data integrity** — strict timestamped OHLC validation for duplicates, ordering, timeframe alignment, timezone normalization, and malformed values at the realtime boundary.
19. **Realtime data** — closed-candle monitoring with duplicate suppression and nearest-zone selection.
20. **Realtime replay** — historical harness that feeds the same realtime monitor path deterministically, without creating a second strategy.
21. **Paper session** — next-bar paper entry, lifecycle management, and append-only event journaling.
22. **Execution recovery safety** — persistent order state, append-only audit chain, fail-closed recovery consistency checks, and durable multi-order restart recovery.
23. **Broker contract safety** — normalized symbol identity, price precision, and volume min/max/step validation before the execution boundary.
24. **Position reconciliation safety** — optional average-entry tracking plus broker symbol/volume contract validation; mismatches fail closed.
25. **System readiness gate** — final fail-closed pre-execution contract across strategy, data, portfolio risk, trade risk, broker contract, reconciliation, execution recovery, and optional ML evidence.
26. **Paper broker simulator** — deterministic full/partial fill, rejection, disconnect/timeout ambiguity, idempotency and position-snapshot semantics for execution/recovery testing.
27. **Integration facade** — `strategy.pipeline.run_research()` connects the core research stages into one consistent API.
28. **Webaria Signal Advisor** — browser UI for realtime signal inspection, Entry/Stop references, score and paper-risk planning using the Worker signal API.
29. **Webaria MTF Signal Advisor** — 1D -> 4H -> 1H -> 15M dashboard. Higher timeframes filter the existing 15M setup and cannot create a new entry pattern.
30. **Webaria signal journal** — browser-local snapshots of advisor outputs for research review; this is not a broker execution log and is not synchronized between devices.
31. **Webaria Paper Risk Engine** — browser-safe risk sizing, stop validation, P/L and conservative bar-exit semantics, isolated from broker execution.
32. **Signal-event identity** — deterministic `sig_...` IDs for replay/realtime signal snapshots, with canonical Python/Worker payload semantics and browser journal deduplication.
33. **Causal outcome labeling** — paper/replay signal outcomes use only candles strictly after the signal bar and preserve explicit `AMBIGUOUS` results when OHLC cannot reveal intrabar order.
34. **Replay outcome attachment** — completed realtime replay results can be enriched with outcome records while keeping the strategy decision immutable.
35. **Research & innovation rules** — hypothesis-driven invention, measurable experiments, evidence-based retention, explicit failure reporting, reproducibility, and fail-closed safety boundaries. The runtime strategy boundary enforces the executable research contract.
36. **Polyglot Verification Fabric** — a language-neutral JSONL contract and fail-closed worker runner for independent validators/research workers across the requested language ecosystem. Language diversity validates or researches existing decisions; it never bypasses safety gates or creates a third strategy direction.
37. **Paper accounting engine** — deterministic realized/unrealized P/L, equity, peak equity, drawdown, drawdown percentage, win/loss statistics, and validated account checkpoints.
38. **Continuous Paper Runtime** — closed-candle runtime with deterministic stop/target exits, once-per-bar processing, stable paper order identity, atomic checkpoints, and restart recovery.
39. **Paper Trading Dashboard** — runtime lifecycle, balance/equity/P&L/drawdown, position, heartbeat, checkpoint status, event stream, equity curve, snapshot export, recovery controls, and explicit fault injection.
40. **Massive Replay / Soak** — deterministic 10,000-bar replay harness with repeatability checks and both LONG/SHORT exit paths.
41. **Failure Injection + Operational Review** — reproducible timeout, disconnect, reject, partial-fill, missing-position, duplicate-bar, out-of-order-bar, and checkpoint-corruption scenarios with a documented paper/demo release gate.
42. **Historical Data Gate** — strict CSV ingestion for real-market OHLCV fixtures, including schema, geometry, finite values, timezone and chronological checks.
43. **Backtest/Realtime/Paper Parity Certification** — normalized decision-stream certification across all three paths on identical closed candles, with deterministic fingerprints and paper-runtime consumption checks.
44. **Long-Term Paper History** — separate append-only SHA-256 hash-chained equity/accounting history survives checkpoint replacement and fails closed on corruption.
45. **Operational Console** — standalone Webaria console reads authoritative `aria.paper-runtime.v1` state from a Durable Object and exposes heartbeat, lifecycle, account metrics, alerts, history, recovery and export without treating browser state as authoritative.
46. **Crash/Restart Certification** — an actual child process is terminated with `os._exit(137)` and a fresh process must recover the durable state; unresolved execution remains HALT.
47. **Historical Shadow / Soak** — the pinned real EURUSD 5-minute sample is replayed through the certified decision boundary and paper runtime twice to verify deterministic long-duration paper evidence.
48. **Final Release Gate CI** — `.github/workflows/release-gate.yml` combines historical data validation, 10k synthetic soak, three-way parity, process-death recovery and long real-history paper shadow.
49. **Canonical MT5 Web Market Bridge** — Webaria `/api/market` proxies an authenticated runtime `/market` endpoint; MT5 is the chart source of truth and provider fallback is intentionally disabled to prevent price/strategy drift.
50. **Durable Bodyguard Telemetry Bridge** — Webaria `/api/bodyguard/status` reads sanitized runtime SQLite events and heartbeat data, giving the dashboard near-real-time durable incident visibility without exposing IPs, secrets, request bodies or PII.
51. **Canonical MT5 strategy boundary** — MT5-sourced `/api/strategy` requests pass through the realtime feed-integrity guard before strategy evaluation, including epoch timestamp normalization and duplicate-cursor protection.
52. **Webaria MT5 single-source runtime** — `/api/market` and `/api/signal` consume the same MT5 market store; the browser evaluates strategy on completed MT5 candles and fails closed on broker-data mismatch or unavailability.
53. **MT5 end-to-end contract certification** — a Python bridge-shaped payload is exercised through the JavaScript `Mt5MarketStore` and canonical `/api/signal` adapter in CI, including completed/forming separation and fail-closed contract checks.
54. **MT5 snapshot fingerprint certification** — the Python bridge, Durable Object market store, signal adapter, Pages compatibility path, and browser runtime share a deterministic SHA-256 identity for the completed-candle snapshot; chart/strategy mismatches fail closed.

## Key modules

- `strategy/backtest.py` — chronological backtest with parity-aligned all-zone signal selection.
- `strategy/historical_data.py` — strict external historical OHLCV CSV loader.
- `strategy/realtime.py` — closed-candle realtime monitor with feed-integrity gating and deterministic event identity.
- `strategy/realtime_replay.py` — deterministic historical replay of the realtime monitor plus causal outcome attachment.
- `strategy/parity_certification.py` — normalized Backtest/Realtime/Paper decision-stream certificate.
- `strategy/paper_accounting.py` — realized/unrealized P/L, equity, peak-equity and drawdown accounting.
- `strategy/paper_history.py` — durable append-only hash-chained paper accounting history.
- `strategy/paper_runtime_checkpoint.py` — atomic versioned continuous-runtime checkpoint persistence.
- `strategy/paper_runtime_engine.py` — continuous closed-candle paper runtime, restart recovery and deterministic exits.
- `strategy/paper_soak.py` — deterministic 10,000-bar replay and failure-injection harness.
- `strategy/historical_shadow.py` — repeated long-duration paper replay over real historical data.
- `strategy/release_gate.py` — final paper-only historical/parity/crash/shadow release checks.
- `live/mt5_market_bridge.py` — read-only Windows-host MT5 market bridge with authenticated `/market` and optional Webaria ingest push.
- `worker/paper_runtime_store.js` — Durable Object implementation of the authoritative paper-runtime state contract.
- `worker/realtime_feed_guard.js` — closed-candle validation shared by the Worker realtime signal path and MT5 strategy boundary.
- `worker/signal_parity_v2.js` — canonical MT5-backed realtime signal adapter used by Webaria `/api/signal`.
- `worker/mt5_market.js` — authoritative MT5 market snapshot store and canonical completed-candle fingerprint source.
- `Webaria/live-market.js` — browser live market loop that keeps chart and strategy on the same MT5 source and rejects mixed snapshots.
- `tests/e2e_mt5_contract.py` + `tests/e2e_mt5_contract.test.mjs` — cross-language MT5 contract certification used by CI.
- `tests/test_mt5_snapshot_fingerprint.mjs` — completed-candle fingerprint and chart/strategy fail-closed regression suite.

## Safety boundary

Ariatrading's supported runtime is **PAPER/DEMO only**. The release gate has no real-broker execution path, and the supported bot configuration rejects `BOT_MODE=live`. A passing paper gate is engineering/research evidence only; it is not a profitability claim and does not authorize real-money trading.
