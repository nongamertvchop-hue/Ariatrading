# Ariatrading Version

Current version: **0.16.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.16.0 — final paper release gate

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest signal selection now mirrors realtime selection by evaluating all candidate support/resistance zones and using the same score/tie semantics.
- Real historical EURUSD 5-minute OHLCV validation is part of CI using a pinned external dataset commit, with strict schema, geometry, timezone and chronological validation.
- Realtime replay, backtest and paper runtime are checked on the same historical window; supervisor filtering remains a separate safety layer.
- Continuous Paper Runtime persists atomic checkpoints and a separate append-only SHA-256 hash-chained long-term accounting history.
- Hard process termination is explicitly tested: unresolved pending execution after restart remains HALT and is never promoted to a synthetic fill.
- Paper accounting exposes realized/unrealized P/L, equity, peak equity, drawdown, drawdown percentage and trade statistics.
- Deterministic 10,000-bar soak/replay and explicit failure injection remain mandatory release evidence.
- Webaria includes an Operational Console with health, lifecycle, heartbeat, last completed bar, balance, equity, P/L, drawdown, position, alerts, checks, equity chart, event history, recovery and snapshot export.
- Security/operational review is documented in `docs/RELEASE_GATE.md` plus the existing paper operational review.
- MT5 remains read-only and no real broker execution path is implemented.

## Release interpretation

A 0.16.0 PASS means the tested engineering properties held for the selected code revision and historical fixture. It does not establish profitability, future performance, or permission to use real money.

## Next milestone

### 1.0.0 — only after extended paper evidence
- Extend historical coverage and long-duration paper observation.
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
