# Ariatrading Version

Current version: **0.8.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.8.1

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure, fake-breakout sequencing, MTF context, setup scoring, risk planning, and realtime closed-candle monitoring remain connected through the existing engine.
- Timestamp-aligned MTF context excludes higher-timeframe candles that have not fully closed at the entry timestamp.
- Sequential backtests can use timestamp-aligned MTF context and the optional execution-friction model.
- Historical execution simulation models spread, commission, slippage, bar-based latency, session boundaries and price precision without placing orders.
- A high-level `strategy.pipeline.run_research()` facade now runs backtest -> execution simulation -> metrics -> chronological split -> bootstrap uncertainty as one consistent research workflow.
- Package exports expose the main engine, execution model and research facade from `strategy`.
- Integration tests cover the end-to-end research facade.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.9.0 — Paper/dry monitoring
- Build a non-ordering monitoring runner with event logs and deterministic replay.
- Validate realtime behavior against historical replay before considering any execution architecture.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine.
