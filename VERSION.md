# Ariatrading Version

Current version: **0.10.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.10.0

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
- ML research now includes feature drift diagnostics, fold-level OOS behavior diagnostics, and an explicit evidence-readiness policy that can require regime, stability, robustness, behavior, and drift evidence.
- Optional PyTorch research now provides causal LSTM and Transformer sequence models as challenger/meta-filters. They cannot create trade direction and are not connected to broker execution.
- Deep-learning normalization is fitted on training sequences only, test sequences remain untouched during optimization, and Transformer sequences include explicit temporal positional encoding.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.10.x — ML and research hardening
- Add fold-by-fold deep-learning walk-forward orchestration for LSTM and Transformer challengers.
- Add persistent deep-learning experiment fingerprints and model configuration provenance.
- Compare classical ML, LSTM and Transformer only on untouched OOS evidence; never select a winner using the final OOS window.
- Add adversarial data-quality tests and execution-friction sensitivity reports.
- Cross-check realtime monitoring against deterministic historical replay.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine.
