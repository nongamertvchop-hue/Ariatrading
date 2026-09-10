# Ariatrading Version

Current version: **0.18.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.18.0 — LIVE Stage 3 production gate

- Stage 3 is a production-readiness boundary, not an increase in the Stage 2 risk budget.
- The hard Stage 2 risk envelope remains: maximum 0.50% risk per trade and 2% daily drawdown.
- Stage 3 permits at most two explicitly allow-listed symbols, two open positions, and four orders per rolling hour.
- Market-state guards remain mandatory: maximum 30-point spread and maximum 10-second tick age.
- Operational guards are mandatory: heartbeat age <= 15 seconds, broker/state reconciliation, and a passing startup self-test.
- A kill switch defaults to ON and must be explicitly set to OFF before a Stage 3 policy can be loaded.
- Account identity remains exact-match login + server validation.
- Non-finite numeric values are rejected fail-closed.
- No credentials are committed and CI must never send broker orders.
- The module defines a policy boundary only; it does not create broker connections or send orders.

## Release interpretation

A 0.18.0 PASS means the Stage 3 policy and its tests satisfy the checked engineering invariants. It does not establish profitability, future performance, broker availability, or authorization to use real money.

## Promotion boundary

The supported repository runtime remains PAPER/DEMO. Any real-money activation requires a separately reviewed execution host, broker account configuration, operational monitoring, eligibility/compliance checks, and an independent release decision outside CI.
