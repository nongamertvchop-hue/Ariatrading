# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.10.0**

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
13. **ML diagnostics** — feature drift, fold-level behavior, permutation stability, and evidence consistency checks.
14. **Deep-learning challengers** — optional causal LSTM and Transformer sequence models that score existing signals but cannot create direction.
15. **ML evidence gate** — explicit readiness policy that can require regime, stability, robustness, behavior, drift, and both deep-learning challengers.
16. **Realtime data** — closed-candle monitoring with duplicate suppression and nearest-zone selection.
17. **Realtime replay** — historical harness that feeds the same realtime monitor path deterministically, without creating a second strategy.
18. **Paper session** — next-bar paper entry, lifecycle management, and append-only event journaling.
19. **Execution recovery safety** — persistent order state, append-only audit chain, and fail-closed recovery consistency checks.
20. **Integration facade** — `strategy.pipeline.run_research()` connects the core research stages into one consistent API.

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
- `strategy/backtest.py` — sequential backtest plus bounded research windows, explicit entry timing, and optional MTF/execution integration.
- `strategy/execution.py` — research-only execution-friction simulation and centralized entry/exit price adjustments.
- `strategy/validation.py` — research metrics and chronological validation tools.
- `strategy/walk_forward.py` — rolling out-of-sample research windows.
- `strategy/ml_features.py` — causal signal features and future-only supervised labels.
- `strategy/ml_meta.py` — chronological classical ML meta-filter.
- `strategy/ml_walk_forward.py` — leakage-safe expanding-history ML evaluation.
- `strategy/ml_drift.py` — training-boundary feature distribution drift diagnostics.
- `strategy/ml_behavior.py` — fold-by-fold ML filter impact diagnostics.
- `strategy/ml_stability.py` — permutation feature stability diagnostics.
- `strategy/ml_evidence_gate.py` — explicit ML evidence completeness/readiness policy.
- `strategy/deep_learning.py` — optional PyTorch LSTM and Transformer sequence challengers.
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
- `adapters/mt5_feed.py` — read-only MT5 market-data adapter.

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
        |                         +---- Drift / behavior / stability
        |                         +---- LSTM / Transformer challengers
        |                         +---- ML Evidence Gate
        |
        +---- Realtime path -> Supervisor -> Paper Session -> Journal
                                  |
                                  +---- Realtime historical replay

Execution safety path:
Order State -> Crash-safe Persistence -> Audit Hash Chain -> Recovery Gate
```

The realtime path uses the same strategy engine rather than a separate live strategy:

`MT5 terminal -> MT5BarFeed -> RealtimeMonitor -> engine -> LONG/SHORT/WAIT -> Supervisor -> PaperSessionRunner`

The MT5 adapter is read-only. It does not call `order_send()`.

## ML and deep-learning research rules

The ML layer is a **meta-filter**, not a third trading setup. The deterministic engine must first produce a valid LONG or SHORT signal. A model may reject or score that signal, but it cannot invent a new entry direction.

All supervised evaluation must preserve chronology:

- features at decision index use only candles available at or before that index;
- future candles are used only for labels;
- training labels must finish before the OOS boundary;
- normalization statistics are fitted on training sequences only;
- OOS samples never update model weights;
- final OOS data must not be used for threshold/model selection.

`strategy/deep_learning.py` provides two challenger architectures:

- **LSTM** — recurrent sequence encoder for temporal dependencies.
- **Transformer** — self-attention sequence encoder with explicit positional encoding.

PyTorch is optional and isolated from the core strategy. Install `requirements-ml.txt` when running deep-learning research. The models are deliberately not connected to MT5 order execution.

The `MLEvidencePolicy` can require both LSTM and Transformer evidence. This is intentionally a **comparison requirement**, not a winner-selection mechanism: the system records both results so a researcher can inspect untouched OOS behavior without silently promoting whichever model looks best in-sample.

## ML evidence gate

`evaluate_ml_evidence_gate()` is a readiness check, not a profitability claim. By default it expects trained OOS folds plus regime, feature-stability, execution-robustness, fold-level behavior, and feature-drift evidence. Deep learning can be made mandatory with `MLEvidencePolicy(require_deep_learning=True)`; when enabled, both LSTM and Transformer evidence can be required.

A `READY` result means the requested evidence exists and passes structural checks. It does **not** mean the strategy is profitable or safe for live money.

## Timestamp-aligned MTF

`build_timestamp_aligned_mtf_context()` accepts timestamped OHLC candles and a signal-candle close timestamp. A candle is usable only when:

`candle_open_time + timeframe_duration <= entry_timestamp`

This prevents a still-forming 1h/4h/1D candle from influencing a lower-timeframe historical decision. `run_backtest()` can inject this aligned context into scoring.

## Integrated research API

Use `strategy.pipeline.run_research()` when a single coherent result is preferred. It performs:

1. sequential strategy backtest;
2. optional execution-friction simulation;
3. descriptive research metrics;
4. chronological train/validation/out-of-sample split;
5. bootstrap expectancy uncertainty interval.

For rolling out-of-sample validation, use `strategy.walk_forward.walk_forward_backtest()`. This is an expanding-history evaluation tool, not a parameter optimizer or a claim of future profitability.

The components remain separately callable for unit testing and research experiments.

## Backtest entry timing

`run_backtest()` exposes an explicit `entry_timing` parameter:

- `signal_reference` — preserves the original historical assumption and uses the strategy confirmation reference on the signal candle.
- `next_bar_open` — fills at the next candle's open and begins exit monitoring only after that fill candle, matching the paper-session lifecycle.

The default remains `signal_reference` for backward compatibility. For research intended to mirror the realtime paper path, use `next_bar_open` consistently in both `run_backtest()` and `walk_forward_backtest()`.

## Execution-cost consistency

Execution price adjustments are centralized in `strategy.execution`:

- `entry_price()` applies spread/slippage once to the reference fill.
- `exit_price()` applies the opposite-side spread/slippage once at exit.
- A risk plan can be built from an already-adjusted entry and passed to `simulate_realistic_exit(..., entry_is_effective=True)` to prevent double application.
- Backtest and paper simulation use the same entry/exit price semantics.

This keeps risk geometry and realized research economics aligned when execution friction is enabled.

## Backtest and execution assumptions

- Only closed historical information is used to construct zones and structure.
- Confirmed swings require right-side confirmation candles.
- A signal requires a separate reaction/test and confirmation sequence.
- Historical backtest entry timing is explicit; the legacy default is the signal reference, while paper-session-compatible research uses next-bar open.
- Paper-session entry from a realtime signal uses the next bar's open.
- Stop is beyond the reaction zone by an adaptive buffer.
- Default target is 2R.
- One hypothetical paper position is allowed at a time.
- If stop and target are both touched in one OHLC candle, stop is assumed first.
- Execution simulation is optional and separate from strategy logic.
- Commission is represented in price units rather than account currency.
- No broker order is submitted anywhere in the repository.

## Walk-forward validation

`walk_forward_backtest()` repeatedly evaluates non-overlapping test windows. Each fold retains all earlier candles as history, while strategy decisions inside the test window only see candles available before each decision. Exit simulation is capped at the fold boundary, preventing a trade in one OOS window from consuming future observations in another window. The same explicit `entry_timing` option is propagated into each fold.

This reduces a common validation mistake: reporting performance from a full-sample backtest as though it were untouched future data. Walk-forward evaluation is still historical evidence, not proof of profitability.

## Realtime historical replay

`replay_realtime_monitor()` feeds chronological historical prefixes into the actual `RealtimeMonitor`. The harness normalizes evaluation timestamps to deterministic replay boundaries, making repeated runs comparable while preserving the monitor's closed-bar, duplicate-suppression, forecast and supervisor logic.

It is a consistency harness, not an additional strategy. Future candles are never included in the prefix for an earlier replay point.

## Paper monitoring

The paper session runner is deliberately non-ordering. It records each evaluated signal, fills approved signals at the next bar's open, manages the existing position before evaluating a new entry opportunity, and ignores duplicate/old candles. Journal events are append-only and can be exported as plain dictionaries for later analysis.

## Validation

The validation layer is deliberately descriptive. It reports historical behavior; it does not prove future profitability. Parameter selection should be performed on training data, checked on validation data, and finally evaluated on untouched out-of-sample data. Robustness checks should include multiple time periods, execution-cost assumptions, and conservative OHLC ambiguity handling.

## Testing

The `tests/` directory covers candle/zone behavior, sequence logic, fake-breakout protection, market structure, MTF look-ahead protection, scoring, risk, baseline and realistic execution simulation, bounded backtesting, entry-timing semantics, execution-cost consistency, validation, walk-forward windows, ML walk-forward provenance, ML drift, ML behavior, ML stability, ML evidence readiness, realtime state handling, deterministic realtime replay, paper trading, paper-session lifecycle, journaling, order persistence/recovery, execution audit integrity, and the integrated research facade.

The deep-learning implementation is optional in the default CI path because PyTorch is a large dependency. `requirements-ml.txt` provides the explicit ML environment for LSTM/Transformer experiments.

## Version / continuation protocol

Current version: **0.10.0**.

At the start of a new chat:

1. Read `VERSION.md` and this README.
2. Inspect latest Git history and GitHub Actions status.
3. Identify the current milestone and unfinished work.
4. Inspect newly added files before making changes.
5. Continue existing modules instead of recreating them.
6. Any behavior change gets a test or an explicit reason why a test is impractical.
7. Update the version only when the change matches semantic-versioning rules.

## Important

This repository is for programming practice and historical/realtime market-data research. It does not establish that a strategy is profitable. It is intentionally read-only with respect to MT5 trading actions. Any future execution architecture must remain isolated from the research engine and should only be considered after robust out-of-sample validation.
