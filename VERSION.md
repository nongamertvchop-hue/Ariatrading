# Ariatrading Version

Current version: **0.18.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability or execution capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.18.0 — LIVE Stage 2 controlled execution

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- PAPER/DEMO research semantics remain unchanged.
- LIVE Stage 2 adds a separately numbered, explicitly armed production envelope instead of weakening the Stage 1 controls.
- Stage 2 allows 1–2 explicitly allow-listed symbols on the operator's MT5 account.
- Stage 2 caps risk at 0.50% per trade, daily equity drawdown at 2%, spread at 30 points and broker tick age at 10 seconds.
- LIVE still requires exact MT5 login/server identity, explicit operator opt-in and non-secret host configuration.
- LIVE still uses completed candles, broker-contract validation, mandatory Stop Loss, `order_check`, deterministic execution journaling, reconciliation and fail-closed ambiguous outcomes.
- Both hardened runtime entry points select the numbered LIVE stage from `ARIATRADING_LIVE_STAGE` and fail closed for an unsupported or unarmed stage.
- CI remains the verification boundary; CI does not send real broker orders.
- No credentials or private account identifiers are committed to Git.

## Release interpretation

A 0.18.0 PASS means the tested engineering properties held for the selected code revision. It does not establish profitability, future performance, or low financial risk.

## Stage 2 activation boundary

Stage 2 is a narrow production execution tier for controlled forward operation. The repository supplies the execution code and hard policy; actual activation requires an eligible MT5 execution host and operator-supplied account credentials/identity outside source control.

## Next milestone

### Production Stage 3 — only after Stage 2 evidence
- Require measured Stage 2 stability and execution evidence before any further increase in symbols, risk or operational limits.
- Keep strategy changes and execution-policy changes isolated.
