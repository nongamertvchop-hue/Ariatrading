# Ariatrading Version

Current version: **0.13.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.13.1

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure, fake-breakout sequencing, MTF context, setup scoring, risk planning, and realtime closed-candle monitoring remain connected through the existing engine.
- Timestamp-aligned MTF context excludes higher-timeframe candles that have not fully closed at the entry timestamp.
- Sequential backtests support bounded evaluation windows so research can isolate out-of-sample periods without allowing exits to cross the test boundary.
- Backtest entry timing is explicit: the legacy signal-reference assumption remains available, while `next_bar_open` matches the paper-session lifecycle.
- Historical execution simulation models spread, commission, slippage, bar-based latency, session boundaries and price precision without placing orders.
- Execution price adjustments are centralized so backtest and paper risk geometry can use the same execution-adjusted entry without double-counting entry costs.
- A high-level `strategy.pipeline.run_research()` facade can propagate the same entry-timing assumption into the backtest.
- Rolling `strategy.walk_forward.walk_forward_backtest()` provides expanding-history, out-of-sample test windows with deterministic fold metrics and the same entry-timing option.
- A deterministic realtime replay harness feeds historical prefixes into the actual `RealtimeMonitor` path without introducing a second strategy implementation.
- Paper monitoring uses a next-bar-open fill model, single-position lifecycle management, duplicate-bar protection, and append-only SIGNAL/OPEN/CLOSE journaling.
- Package exports expose the main strategy, backtest timing, execution helpers, paper, replay, and walk-forward research APIs.
- ML research includes feature drift diagnostics, fold-level OOS behavior diagnostics, model-health/calibration diagnostics, and an explicit evidence-readiness policy that can require regime, stability, robustness, behavior, drift, and deep-learning challenger evidence.
- Optional PyTorch research provides causal LSTM and Transformer sequence models as challenger/meta-filters. They cannot create trade direction and are not connected to broker execution.
- Deep-learning normalization is fitted on training sequences only, test sequences remain untouched during optimization, and Transformer positional encoding is robust to odd hidden dimensions.
- Fold-by-fold `deep_learning_walk_forward_backtest()` now evaluates LSTM and Transformer challengers on expanding chronological OOS windows using the same strategy-generated signal evidence and training-label boundaries as classical ML.
- The final system readiness gate combines strategy protection, realtime data quality, portfolio risk, trade risk, position reconciliation, execution recovery, and optional ML evidence into one fail-closed pre-execution contract.
- New-entry readiness now explicitly requires the reconciled broker state to be flat; a safely reconciled existing position cannot accidentally pass a new-entry gate.
- `RiskLimits.min_quantity` is enforced as a hard broker-quantity constraint both before and after a maximum-quantity cap/step floor.
- ML evidence drift diagnostics now fail closed on every non-finite statistic.
- A deterministic paper-broker simulator now models full/partial fill, rejection, connection loss, timeout-after-accept ambiguity, idempotent client-order replay, and position snapshots for reconciliation tests. It is fully isolated from MT5 and cannot place real orders.
- End-to-end paper execution now persists the complete order registry across transitions, verifies audit/state agreement before restart recovery, and halts on corrupt state or ambiguous broker state rather than treating it as a fresh order.
- Portfolio daily-loss accounting now combines independently recorded realized loss with session-equity loss using the maximum rather than summing both sources, preventing double counting while preserving a fail-closed limit.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.13.x — production-boundary hardening
- Add broker-symbol contract validation for point/digits, volume min/max/step, and price precision using normalized adapter metadata only.
- Add adversarial feed tests for timezone ambiguity, duplicate sequences, timestamp gaps, OHLC inconsistencies, and out-of-order updates.
- Add persistent deep-learning experiment fingerprints and model configuration provenance.
- Compare classical ML, LSTM and Transformer only on identical untouched OOS windows; never select a winner using the final OOS window.
- Route all future paper/live candidates through the system readiness gate before any broker adapter is permitted to act.
- Add execution-friction sensitivity reports and historical replay parity checks.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
