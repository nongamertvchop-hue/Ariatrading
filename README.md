# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.13.1**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No unrelated entry patterns are added. Context layers can filter, score, or validate these two setups, but cannot create a third setup.

## Architecture

The project is layered so every stage can be used together without duplicating strategy rules:

1. **Market structure** — confirmed swing highs/lows are labeled HH, HL, LH and LL, producing a structural bias.
2. **Zone intelligence** — repeated confirmed swings form support/resistance zones.
3. **Candle intelligence** — completed candles provide descriptive buying/selling pressure.
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
17. **Realtime data** — closed-candle monitoring with duplicate suppression and nearest-zone selection.
18. **Realtime replay** — historical harness that feeds the same realtime monitor path deterministically, without creating a second strategy.
19. **Paper session** — next-bar paper entry, lifecycle management, and append-only event journaling.
20. **Execution recovery safety** — persistent order state, append-only audit chain, and fail-closed recovery consistency checks.
21. **System readiness gate** — final fail-closed pre-execution contract combining strategy protection, data quality, portfolio risk, trade risk, position reconciliation, execution recovery, and optional ML evidence.
22. **Paper broker simulator** — deterministic full/partial fill, rejection, disconnect/reconnect, timeout-after-accept ambiguity, idempotency and position-snapshot semantics for execution/recovery testing.
23. **End-to-end paper recovery** — durable multi-order lifecycle across restart, broker reconciliation, audit verification, and fail-closed corruption handling.
24. **Portfolio risk accounting** — realized-loss and session-equity loss are combined conservatively without double counting.

## Key modules

- `strategy/candles.py` — candle structure and descriptive pressure.
- `strategy/levels.py` — legacy detector kept for compatibility.
- `strategy/levels_v2.py` — primary confirmed-swing zones.
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
- `strategy/deep_learning_walk_forward.py` — fold-by-fold chronological LSTM/Transformer research.
- `strategy/research_validation.py` — aggregated, fingerprinted research evidence.
- `strategy/research_audit.py` — temporal and evidence consistency checks.
- `strategy/research_gate.py` — baseline research evidence completeness gate.
- `strategy/realtime.py` — closed-candle realtime monitor.
- `strategy/realtime_replay.py` — deterministic historical replay of the realtime monitor.
- `strategy/paper.py` — deterministic single-position paper simulator.
- `strategy/paper_session.py` — realtime-to-paper orchestration with next-bar entry and idempotency.
- `strategy/journal.py` — SIGNAL/OPEN/CLOSE research event journal.
- `strategy/order_state.py` — deterministic order lifecycle state machine.
- `strategy/order_persistence.py` — crash-safe order-state snapshot persistence.
- `strategy/execution_audit.py` — append-only hash-chain execution audit journal.
- `strategy/execution_recovery.py` — fail-closed post-restart execution consistency gate.
- `strategy/paper_execution_e2e.py` — end-to-end paper submission/recovery coordinator.
- `strategy/system_gate.py` — final fail-closed pre-execution readiness contract.
- `strategy/portfolio_risk.py` — stateful daily-loss, drawdown and consecutive-loss kill switch.
- `adapters/mt5_feed.py` — read-only MT5 market-data adapter.
- `adapters/paper_broker.py` — broker-like paper/demo simulator for deterministic execution tests.

## System flow

```text
OHLC / MT5 closed bars
        |
        v
Timeframe normalization
        |
        v
Confirmed S/R zones <---- Market Structure
        |
        v
Core Sequence Engine
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM
        |
        +---- Fake Breakout protection
        +---- MTF context / look-ahead protection
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
        |                         +---- DL walk-forward folds
        |                         +---- ML Evidence Gate
        |
        +---- Realtime path -> Supervisor -> Paper Session -> Journal
                                  |
                                  +---- Realtime historical replay

Paper execution validation path:
System Gate -> Order State -> Persistence -> Audit -> Paper Broker
                    |                         |
                    +---- idempotency         +---- position snapshots
                    +---- partial/rejected    +---- reconnect/timeout
                    |
                    v
              Reconciliation -> Recovery verification -> ALLOW / HALT
```

The realtime path uses the same strategy engine rather than a separate live strategy:

`MT5 terminal -> MT5BarFeed -> RealtimeMonitor -> engine -> LONG/SHORT/WAIT -> Supervisor -> PaperSessionRunner`

The MT5 adapter remains read-only. There is no live order-sending implementation in this repository.
