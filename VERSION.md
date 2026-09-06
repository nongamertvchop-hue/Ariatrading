# Ariatrading Version

Current version: **0.9.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.9.0

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure, fake-breakout sequencing, MTF context, setup scoring, risk planning, and realtime closed-candle monitoring remain connected through the existing engine.
- Timestamp-aligned MTF context excludes higher-timeframe candles that have not fully closed at the entry timestamp.
- Sequential backtests support bounded evaluation windows so research can isolate out-of-sample periods without allowing exits to cross the test boundary.
- Historical execution simulation models spread, commission, slippage, bar-based latency, session boundaries and price precision without placing orders.
- A high-level `strategy.pipeline.run_research()` facade runs backtest -> execution simulation -> metrics -> chronological split -> bootstrap uncertainty as one consistent research workflow.
- Rolling `strategy.walk_forward.walk_forward_backtest()` provides expanding-history, out-of-sample test windows with deterministic fold metrics.
- Paper monitoring uses a next-bar-open fill model, single-position lifecycle management, duplicate-bar protection, and append-only SIGNAL/OPEN/CLOSE journaling.
- Package exports expose the main strategy, paper, replay, and walk-forward research APIs.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.9.x — Robustness and research hardening
- Add adversarial data-quality tests and execution-friction sensitivity reports.
- Cross-check realtime monitoring against deterministic historical replay.
- Add research outputs that compare walk-forward folds without selecting parameters on the final OOS window.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine.
