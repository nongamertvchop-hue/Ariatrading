# Ariatrading

Educational price-action research and paper-automation project for EURUSD-style OHLC data.

**Current version: 0.15.0**

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
32. **Automatic paper runtime** — `live/paper_runtime.py` continuously drives the existing realtime -> paper session path on newly closed candles, exposes runtime health/account snapshots, and fails closed on unexpected runtime errors. DEMO mode is explicitly disabled until a broker execution adapter exists.
33. **Deterministic signal identity** — paper signal journal events have stable IDs derived from the closed-bar decision boundary, enabling duplicate-safe polling and replay.

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
        +---- Realtime path -> Supervisor -> Paper Automation Runtime
                                  |
                                  +---- Realtime historical replay
                                  |
                                  +---- Paper Session -> Paper Risk/Lifecycle
                                  |       |
                                  |       +---- deterministic signal ID
                                  |       +---- next-bar entry
                                  |       +---- journal
                                  |
                                  +---- Webaria Signal Advisor
                                          |
                                          +---- 1D -> 4H -> 1H -> 15M filter
                                          +---- Entry / Stop / Score inspection
                                          +---- browser-local signal journal

Future demo execution boundary (disabled):
Paper-validated signal
        |
        v
System Gate -> Broker Contract -> Order State -> Persistence -> Audit
                                      |
                                      v
                               MT5 Demo Adapter
                                      |
                             Position Reconciliation
                                      |
                                      v
                              Recovery verification
                                      |
                                ALLOW / HALT
```

The realtime path uses the same strategy engine rather than a separate live strategy:

`MT5 terminal -> MT5BarFeed -> feed integrity -> RealtimeMonitor -> engine -> LONG/SHORT/WAIT -> Supervisor -> PaperAutomationRuntime -> PaperSessionRunner`

The Webaria Advisor path uses the Worker API for market-data analysis:

`Twelve Data -> Cloudflare Worker /api/signal -> Webaria Signal Advisor -> MTF filter -> Paper Risk Planner`

The MT5 adapter remains read-only. There is no live or demo order-sending implementation in this repository yet.

## Validation principles

Research is descriptive evidence, not a profitability guarantee. Features at a decision index use only information available at or before that index. Future candles are used for labels only. Training boundaries, normalization, model challengers and final OOS evaluation remain chronologically separated. Any ambiguous execution, contract mismatch, or corrupted recovery state fails closed rather than being retried blindly.

The MTF Advisor is deliberately conservative: it cannot invent LONG/SHORT direction. It can only pass through an existing lower-timeframe setup when higher-timeframe structure does not contradict it. A lack of alignment produces WAIT rather than forcing a trade direction.

Webaria Paper Trading and the Python Paper Automation Runtime are simulation-only. Browser-local state and in-memory signal journals are useful for testing the interface and research workflow but are not durable multi-device broker execution records.

## Testing

The `tests/` directory covers candle/zone behavior, sequence logic, fake-breakout protection, market structure, MTF look-ahead protection, scoring, risk and quantity constraints, baseline and realistic execution simulation, bounded backtesting, entry-timing semantics, execution-cost consistency, validation, walk-forward windows, ML walk-forward provenance, ML drift, ML behavior, ML stability, ML model health, ML evidence readiness, fixed-window ML challenger comparison, deep-learning sequence causality, deep-learning walk-forward contracts and provenance persistence, realtime state handling, feed-integrity boundary behavior, deterministic realtime replay, paper trading, paper-session lifecycle, journaling, paper-broker failure semantics, paper-position reconciliation semantics including average-entry and broker-contract mismatches, order persistence/recovery, execution audit integrity, broker contract validation, the integrated research facade/system gate, Webaria paper-risk behavior, the single-timeframe Signal Advisor contract, the multi-timeframe Signal Advisor contract, deterministic signal-event identity, and the automatic paper runtime fail-closed loop.

The deep-learning implementation is optional in the default CI path because PyTorch is a large dependency. `requirements-ml.txt` provides the explicit ML environment for LSTM/Transformer experiments.

## Version / continuation protocol

Current version: **0.15.0**.

At the start of a new chat:

1. Read `VERSION.md` and this README.
2. Inspect latest Git history and GitHub Actions status.
3. Identify the current milestone and unfinished work.
4. Inspect newly added files before making changes.
5. Continue existing modules instead of recreating them.
6. Any behavior change gets a test or an explicit reason why a test is impractical.
7. Update the version only when the change matches semantic-versioning rules.

## Important

This repository is for programming practice and historical/realtime market-data research. It does not establish that a strategy is profitable. It is intentionally read-only with respect to MT5 trading actions. Any future execution architecture must remain isolated from the research engine and should only be considered after robust out-of-sample validation and sustained paper/demo testing.
