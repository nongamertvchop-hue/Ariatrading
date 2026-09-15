# Ariatrading Version

Current version: **0.17.5**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.5 — ABCD parity guardrails

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics remain on one normalized three-way decision stream.
- Three-way parity certification now fails closed on duplicate or non-monotonic decision timestamps.
- Parity certification now reports decisions present in one source stream but missing from the other instead of silently comparing only an intersection.
- Regression coverage was added for duplicate Realtime timestamps and an unmatched Backtest decision.
- The MT5 bridge remains read-only and the runtime remains PAPER/DEMO-only.
- Webaria remains MT5 single-source for chart and strategy; `/api/signal` does not fall back to a synthetic provider.

## Release interpretation

A 0.17.5 PASS means the tested engineering properties held for the selected code revision and fixtures. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
