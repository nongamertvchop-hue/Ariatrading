# Ariatrading Version

Current version: **0.17.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.1 — final paper certification

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper decision semantics are certified through one normalized three-way decision stream.
- A real child-process termination test verifies durable checkpoint + restart recovery; unknown execution remains fail-closed HALT.
- A 10,000-bar deterministic paper soak remains required, plus a 10,000-bar shadow run over pinned real EURUSD 5-minute historical data.
- The Operational Console reads the `aria.paper-runtime.v1` contract from a Durable Object and refuses to treat browser-local state as authoritative.
- The durable contract carries lifecycle, heartbeat, account/equity, position, pending state, alerts, history, events, recovery snapshot and export data.
- The runtime publishing page remains PAPER/DEMO only; the supported configuration rejects `BOT_MODE=live`.
- No real broker order path is enabled by the release gate or supported bot configuration.

## Release interpretation

A 0.17.1 PASS means the tested engineering properties held for the selected code revision and historical fixture. It does not establish profitability, future performance, or authorization to use real money.

## Promotion boundary

Real-money execution is outside the supported runtime in this repository. Further promotion requires a separately reviewed architecture, independent risk controls, compliance/eligibility review, and a safe execution environment; it is not enabled by the paper release gate.
