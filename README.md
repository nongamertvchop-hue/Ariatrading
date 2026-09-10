# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.16.1**

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
43. **Backtest/Realtime/Paper Parity Gate** — backtest and realtime now share all-zone candidate selection and score/tie semantics; release validation compares the common decision boundary and paper-runtime determinism on the same historical window.
44. **Long-Term Paper History** — separate append-only SHA-256 hash-chained equity/accounting history survives checkpoint replacement and fails closed on corruption.
45. **Operational Console** — standalone Webaria console for health, heartbeat, lifecycle, live market reachability, account metrics, alerts, release checks, event history, equity visualization and snapshot export.
46. **Final Release Gate CI** — `.github/workflows/release-gate.yml` downloads a pinned real EURUSD 5-minute historical sample and runs the final paper-only gate plus the full Python regression suite.
47. **Canonical MT5 Web Market Bridge** — Webaria `/api/market` now proxies an authenticated runtime `/market` endpoint; MT5 is the chart source of truth and provider fallback is intentionally disabled to prevent price/strategy drift.
48. **Durable Bodyguard Telemetry Bridge** — Webaria `/api/bodyguard/status` reads sanitized runtime SQLite events and heartbeat data, giving the dashboard near-real-time durable incident visibility without exposing IPs, secrets, request bodies or PII.

## Key modules

- `strategy/backtest.py` — chronological backtest with parity-aligned all-zone signal selection.
- `strategy/historical_data.py` — strict external historical OHLCV CSV loader.
- `strategy/realtime.py` — closed-candle realtime monitor with feed-integrity gating and deterministic event identity.
- `strategy/realtime_replay.py` — deterministic historical replay of the realtime monitor plus causal outcome attachment.
- `strategy/paper_accounting.py` — realized/unrealized P/L, equity, peak-equity and drawdown accounting.
- `strategy/paper_history.py` — durable append-only hash-chained paper accounting history.
- `strategy/paper_runtime_checkpoint.py` — atomic versioned continuous-runtime checkpoint persistence.
- `strategy/paper_runtime_engine.py` — continuous closed-candle paper runtime, restart recovery and deterministic exits.
- `strategy/paper_soak.py` — deterministic 10,000-bar replay and failure-injection harness.
- `strategy/release_gate.py` — final historical/replay/paper parity and operational release checks.
- `strategy/order_state.py` — deterministic order lifecycle state machine.
- `strategy/order_persistence.py` — crash-safe order-state snapshot persistence.
- `strategy/execution_audit.py` — append-only hash-chain execution audit journal.
- `strategy/execution_recovery.py` — fail-closed post-restart execution consistency gate.
- `strategy/paper_trading_loop.py` — end-to-end paper execution coordinator and reconciliation path.
- `strategy/position_reconciliation.py` — normalized local/broker position reconciliation with average-entry and contract checks.
- `strategy/system_gate.py` — final fail-closed pre-execution readiness contract.
- `strategy/broker_contract.py` — normalized broker-symbol contract checks.
- `adapters/mt5_feed.py` — read-only MT5 market-data adapter.
- `adapters/paper_broker.py` — broker-like paper/demo simulator for deterministic execution tests.
- `scripts/run_runtime_api.py` — authenticated REST/WebSocket runtime entrypoint and MT5 market bridge.
- `polyglot/runner.py` — bounded JSONL worker execution and fail-closed consensus validation.
- `Webaria/paper-runtime.html` — Paper Trading Dashboard shell.
- `Webaria/paper-runtime.js` — continuous browser paper runtime and recovery controls.
- `Webaria/operational-console.html` — operational monitoring console.
- `Webaria/bodyguard.html` — durable Bodyguard security telemetry dashboard.
- `Webaria/functions/api/market.js` — canonical Cloudflare-to-MT5 runtime market proxy.
- `Webaria/functions/api/bodyguard/status.js` — sanitized durable Bodyguard telemetry facade.
- `Webaria/signal-advisor.html` — single-timeframe realtime Signal Advisor.
- `Webaria/mtf-advisor.html` — multi-timeframe Signal Advisor and local signal journal.
- `worker/signal_parity.js` — Worker-side low-level strategy parity primitives.
- `worker/signal_parity_v2.js` — Worker realtime orchestration aligned with Python sequence/score semantics.
- `worker/forecast_parity.js` — Worker deterministic forecast and realtime-supervisor parity helpers.
- `worker/realtime_feed_guard.js` — Worker realtime OHLC/timestamp/staleness/deduplication guard.

## System flow

```text
MT5 terminal
    |
    +--> read-only closed bars + forming bar/tick
    |
    v
Authenticated Runtime API (/market, /health, /events)
    |
    +--> Webaria /api/market ----> Trading Chart
    |
    +--> Webaria /api/bodyguard/status ----> Bodyguard Console
    |
    v
Feed integrity + timeframe normalization
    |
    v
Confirmed S/R zones <---- Market Structure
    |
    v
Core Sequence Engine
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM
    |
    +---- Fake Breakout protection
    +---- MTF look-ahead protection
    +---- Setup scoring
    |
    v
LONG / SHORT / WAIT
    |
    +---- Historical path -> Risk -> Backtest -> Validation
    |
    +---- Realtime path -> Supervisor -> Event ID -> Paper Runtime
    |                                                   |
    |                                                   +---- once-only closed candle
    |                                                   +---- checkpoint/restart recovery
    |                                                   +---- position reconciliation
    |                                                   +---- P/L -> Equity -> Drawdown
    |                                                   +---- long-term hash-chained history
    |                                                   +---- Operational Console
    |
    +---- Polyglot Validation Fabric -> independent workers
    |
    +---- Final Release Gate -> CI/security/soak/failure evidence
```

## Research safety contract

Ariatrading is a research and paper/demo system. MT5 integration remains read-only, and the paper runtime does not place or manage real broker orders.

The Paper Trading Dashboard and Operational Console are explicitly **PAPER/DEMO**. Ambiguous execution outcomes remain unresolved until a trustworthy source of truth is available; they are never converted into a synthetic fill merely to keep the runtime moving.

## Final release gate

Version 0.16.1 extends the final paper-only architecture with an authenticated MT5 runtime market bridge, canonical Webaria market sourcing, durable Bodyguard telemetry, and CI syntax coverage for the new edge endpoints. Passing the release gate demonstrates the tested engineering/research properties for the selected revision and fixture. It is **not** evidence of profitability, future performance, or authorization for real-money execution.

## Polyglot implementation status

The language registry covers the requested ecosystem, but this repository does **not** pretend every compiler, VM, scientific suite, GPU toolchain, HDL toolchain, or formal prover is installed. A language becomes operational only when a concrete worker for that runtime is registered and passes the common contract tests. This avoids fake compatibility and prevents a large number of duplicated strategy implementations from becoming a hidden source of semantic drift.
