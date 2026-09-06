# Ariatrading Version

Current version: **0.5.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.5.1

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure is available.
- Fake-breakout classification is integrated into the sequence engine.
- Multi-timeframe context and setup scoring are available.
- Timestamp-aligned MTF context now excludes higher-timeframe candles that have not fully closed at the entry timestamp.
- Automated test workflow remains the project gate.
- Realtime monitoring uses closed candles only and now evaluates each newly closed candle at most once.
- Realtime zone selection is nearest-zone based rather than relying on list order.
- Realtime zone tolerance now adapts to the selected timeframe.
- MT5 integration remains read-only; no order execution is implemented.

## Next milestones

### 0.6.0 — Historical MTF integration
- Feed timestamp-aligned MTF context directly into sequential backtests.
- Add explicit timestamp requirements to historical candle data.
- Test that future higher-timeframe bars cannot affect an earlier entry.

### 0.7.0 — Research validation
- Add train/validation/out-of-sample splits.
- Add expectancy, profit factor, drawdown, trade-count and R-distribution reporting.
- Add parameter-robustness and bootstrap-style uncertainty analysis.

### 0.8.0 — Realistic execution simulation
- Model spread, commission, slippage, latency, session boundaries and symbol precision.
- Keep execution simulation separate from the strategy decision layer.

### 0.9.0 — Paper/dry monitoring
- Build a non-ordering monitoring runner with event logs and deterministic replay.
- Validate realtime behavior against historical replay before considering any execution architecture.

### 1.0.0 — Only after validation
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine.
