# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.15.1**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No unrelated entry patterns are added. Context layers can filter, score, or validate these two setups, but cannot create a third setup.

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
12. **ML meta-filter research** — chronological classical ML filtering of existing LONG/SHORT signals only.
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
32. **MT5 demo execution boundary** — a separate adapter can submit protected orders only when the connected account is explicitly a MetaTrader 5 Demo account; real accounts are rejected.
33. **Demo Auto Trader** — realtime orchestration that consumes the existing monitor and requires an explicit `SystemGateDecision` and risk-plan resolver before a demo order is sent.
34. **Continuous demo runtime** — closed-candle polling loop for a Windows/MT5 host; runtime/execution ambiguity stops the process instead of retrying blindly.
35. **Realtime demo control plane** — a persistent Cloudflare Durable Object stores the demo auto-trading ON/OFF state; Webaria can toggle it from the browser and the MT5 runtime re-checks it before execution.
36. **Realtime demo control UI** — Webaria shows `AUTO ON/OFF` plus demo runtime `ONLINE/OFFLINE` status with short polling; the browser only controls state and never sends MT5 orders.

## Key modules

- `strategy/candles.py` — candle structure, descriptive pressure, and OHLC input invariants.
- `strategy/levels.py` — legacy detector kept for compatibility.
- `strategy/levels_v2.py` — primary confirmed-swing zones, independent reactions, and broken-zone filtering.
- `strategy/market_structure.py` — HH/HL/LH/LL structural context.
- `strategy/sequence.py` — primary two-setup multi-candle logic.
- `strategy/fake_breakout.py` — breakout/reclaim classification.
- `strategy/protection.py` — level safety checks.
- `strategy/timeframe.py` — adaptive distances for 1m through 1D.
- `strategy/mtf.py` — structural context and timestamp alignment.
- `strategy/scoring.py` — explainable setup quality score.
- `strategy/engine.py` — central LONG/SHORT/WAIT strategy interface.
- `strategy/risk.py` — hypothetical risk plans and baseline exit simulation.
- `strategy/risk_engine.py` — account-level sizing and hard risk limits, including broker minimum/maximum quantity.
- `strategy/portfolio_risk.py` — stateful daily-loss, drawdown and consecutive-loss kill switch.
- `strategy/backtest.py` — sequential backtest plus bounded research windows, explicit entry timing, and optional MTF/execution integration.
- `strategy/execution.py` — research-only execution-friction simulation and centralized entry/exit price adjustments.
- `strategy/validation.py` — research metrics and chronological validation tools.
- `strategy/walk_forward.py` — rolling out-of-sample research windows.
- `strategy/ml_features.py` — causal signal features and future-only supervised labels.
- `strategy/ml_meta.py` — chronological classical ML meta-filter.
- `strategy/ml_walk_forward.py` — leakage-safe expanding-history ML evaluation.
- `strategy/ml_drift.py` — training-boundary feature distribution drift diagnostics.
- `strategy/ml_behavior.py` — fold-by-fold ML filter impact diagnostics.
- `strategy/ml_model_health.py` — descriptive performance, calibration, and score-distribution diagnostics.
- `strategy/ml_stability.py` — permutation feature stability diagnostics.
- `strategy/ml_evidence_gate.py` — explicit ML evidence completeness/readiness policy.
- `strategy/ml_model_comparison.py` — fixed-window HGB/LSTM/Transformer challenger comparison without automatic model selection.
- `strategy/deep_learning.py` — optional PyTorch LSTM and Transformer sequence challengers.
- `strategy/deep_learning_walk_forward.py` — fold-by-fold chronological LSTM/Transformer research with optional provenance persistence.
- `strategy/research_provenance.py` — deterministic provenance fingerprints, comparability checks, and atomic persistence.
- `strategy/research_validation.py` — aggregated, fingerprinted research evidence.
- `strategy/research_audit.py` — temporal and evidence consistency checks.
- `strategy/research_gate.py` — baseline research evidence completeness gate.
- `strategy/feed_integrity.py` — strict timestamped OHLC feed validation.
- `strategy/realtime.py` — closed-candle realtime monitor with feed-integrity gating.
- `strategy/realtime_replay.py` — deterministic historical replay of the realtime monitor.
- `strategy/paper.py` — deterministic single-position paper simulator.
- `strategy/paper_session.py` — realtime-to-paper orchestration with next-bar entry and idempotency.
- `strategy/journal.py` — SIGNAL/OPEN/CLOSE research event journal.
- `strategy/order_state.py` — deterministic order lifecycle state machine.
- `strategy/order_persistence.py` — crash-safe order-state snapshot persistence.
- `strategy/execution_audit.py` — append-only hash-chain execution audit journal.
- `strategy/execution_recovery.py` — fail-closed post-restart execution consistency gate.
- `strategy/paper_execution_e2e.py` — end-to-end paper submission/recovery coordinator.
- `strategy/position_reconciliation.py` — normalized local/broker position reconciliation with average-entry and contract checks.
- `strategy/system_gate.py` — final fail-closed pre-execution readiness contract.
- `strategy/broker_contract.py` — normalized broker-symbol contract checks.
- `adapters/mt5_feed.py` — read-only MT5 market-data adapter.
- `adapters/paper_broker.py` — broker-like paper/demo simulator for deterministic execution tests.
- `live/demo_mt5.py` — **DEMO-ONLY** MT5 order adapter with account, symbol, volume, SL/TP, duplicate-position, order-check, and execution-result validation.
- `live/demo_auto_trader.py` — strategy-to-demo execution orchestration through the existing System Gate contract and realtime control switch.
- `live/demo_runtime.py` — continuous closed-candle demo runtime with remote fail-closed ON/OFF control.
- `live/demo_control.py` — HTTPS client for the shared demo control plane.
- `worker/auto_trading_control.js` — Cloudflare Durable Object for persistent demo auto-trading state.
- `Webaria/auto-trading-control.js` — realtime Webaria ON/OFF control and runtime status UI.
- `Webaria/paper-engine.js` — browser-safe paper risk primitives; no broker calls.
- `Webaria/signal-advisor.html` — single-timeframe realtime Signal Advisor.
- `Webaria/mtf-advisor.html` — multi-timeframe Signal Advisor and local signal journal.

## System flow

```text
OHLC / MT5 closed bars
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
        |                         |
        |                         +---- Walk-forward OOS
        |                         +---- Classical ML meta-filter
        |                         +---- Drift / behavior / stability / health
        |                         +---- LSTM / Transformer challengers
        |                         +---- DL walk-forward folds + provenance
        |                         +---- ML Evidence Gate
        |
        +---- Realtime path -> Supervisor -> SystemGate
                                  |
                                  +---- Paper Session -> Paper Broker
                                  |
                                  +---- DEMO Auto Trader
                                  |       |
                                  |       +---- Remote ON/OFF control
                                  |       +---- MT5 Demo Account Guard
                                  |       +---- Symbol/Volume Contract
                                  |       +---- order_check()
                                  |       +---- order_send()
                                  |       +---- SL / TP protection
                                  |       +---- Managed-position protection
                                  |
                                  +---- Webaria Signal Advisor
                                  |       |
                                  |       +---- 1D -> 4H -> 1H -> 15M filter
                                  |       +---- Entry / Stop / Score inspection
                                  |       +---- Browser-local signal journal
                                  |       +---- AUTO ON/OFF + runtime status
                                  |
                                  +---- Webaria Paper Risk Engine
```

The realtime demo execution path uses the same strategy engine rather than a separate strategy:

`MT5 terminal -> MT5BarFeed -> feed integrity -> RealtimeMonitor -> engine -> LONG/SHORT/WAIT -> Supervisor -> SystemGate -> DemoAutoTrader -> MT5DemoExecutionAdapter`

The demo control path is deliberately separate:

`Webaria AUTO ON/OFF -> Cloudflare Worker /api/auto-trading -> Durable Object -> DemoRuntime control client -> execution_enabled() -> DemoAutoTrader`

The Webaria Advisor path uses the Worker API for market-data analysis:

`Twelve Data -> Cloudflare Worker /api/signal -> Webaria Signal Advisor -> MTF filter -> Paper Risk Planner`

MT5 market-data reading remains available through `MT5BarFeed`. Demo order sending is isolated in `live/demo_mt5.py`; **real-account execution is deliberately unsupported and rejected by the adapter.**

## Validation principles

Research is descriptive evidence, not a profitability guarantee. Features at a decision index use only information available at or before that index. Future candles are used for labels only. Training boundaries, normalization, model challengers and final OOS evaluation remain chronologically separated. Any ambiguous execution, contract mismatch, or corrupted recovery state fails closed rather than being retried blindly.

The MTF Advisor is deliberately conservative: it cannot invent LONG/SHORT direction. It can only pass through an existing lower-timeframe setup when higher-timeframe structure does not contradict it. A lack of alignment produces WAIT rather than forcing a trade direction.

Webaria Paper Trading is simulation-only. Browser-local state and signal journals are useful for testing the interface and research workflow but are not durable multi-device execution records.

The MT5 demo runtime requires an explicit control endpoint and secret token. Its control client treats an unreachable or invalid control plane as OFF, and the `DemoAutoTrader` checks that control immediately before the broker call. The browser control endpoint only changes the persistent switch and never submits an MT5 order itself. Cloudflare Durable Objects provide the persistent coordination primitive used for that state.

## Testing

The `tests/` directory covers candle/zone behavior, sequence logic, fake-breakout protection, market structure, MTF look-ahead protection, scoring, risk and quantity constraints, baseline and realistic execution simulation, bounded backtesting, entry-timing semantics, execution-cost consistency, validation, walk-forward windows, ML walk-forward provenance, ML drift, ML behavior, ML stability, ML model health, ML evidence readiness, fixed-window ML challenger comparison, deep-learning sequence causality, deep-learning walk-forward contracts and provenance persistence, realtime state handling, feed-integrity boundary behavior, deterministic realtime replay, paper trading, paper-session lifecycle, journaling, paper-broker failure semantics, paper-position reconciliation semantics including average-entry and broker-contract mismatches, order persistence/recovery, execution audit integrity, broker contract validation, the integrated research facade/system gate, Webaria paper-risk behavior, the single-timeframe Signal Advisor contract, and the demo execution/control contracts.

The deep-learning implementation is optional in the default CI path because PyTorch is a large dependency. `requirements-ml.txt` provides the explicit ML environment for LSTM/Transformer experiments. `requirements-realtime.txt` already contains the MetaTrader5 Python package used by the MT5 feed and demo execution boundary.

## Version / continuation protocol

Current version: **0.15.1**.

At the start of a new chat:

1. Read `VERSION.md` and this README.
2. Inspect latest Git history and GitHub Actions status.
3. Identify the current milestone and unfinished work.
4. Inspect newly added files before making changes.
5. Continue existing modules instead of recreating them.
6. Any behavior change gets a test or an explicit reason why a test is impractical.
7. Update the version only when the change matches semantic-versioning rules.

## Important

This repository is for programming practice and historical/realtime market-data research with a dedicated MT5 demo execution path. It does not establish that a strategy is profitable. **Live/real-account trading is intentionally unsupported.** Any future real execution architecture must remain separately isolated from the research engine and should only be considered after robust out-of-sample and forward-demo validation.
