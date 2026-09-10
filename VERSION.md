# Ariatrading Version

Current version: **0.17.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.17.0 — LIVE Stage 1 execution boundary

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper strategy semantics remain unchanged.
- MT5 real-account execution is now implemented behind an explicit Stage 1 production policy.
- LIVE requires the exact operator opt-in `ARIATRADING_ENABLE_LIVE=I_UNDERSTAND_REAL_ORDERS`.
- LIVE requires an exact account-login and trade-server allowlist supplied outside the repository.
- LIVE Stage 1 permits exactly one configured symbol and enforces a maximum 0.25% risk per trade.
- LIVE Stage 1 enforces a maximum 1% daily equity drawdown, 20-point spread and 5-second broker tick age.
- LIVE continues to use completed-candle evaluation, broker contract validation, mandatory Stop Loss, `order_check`, idempotency, reconciliation and fail-closed ambiguous outcomes.
- The canonical hardened runtime is `live/runtime_cli.py` / `live/live_runtime_cli.py`; the legacy runner is also constrained by the Stage 1 policy.
- No broker credentials, account identifiers or live secrets are committed to Git.

## Release interpretation

A 0.17.0 PASS means the tested engineering properties held for the selected code revision. It does not establish profitability, future performance, or low financial risk. Real-money activation still requires operator-supplied MT5 credentials, exact account/server allowlisting and an eligible production host with the MT5 terminal available.

## Stage 1 activation boundary

Stage 1 is deliberately a narrow real-money execution tier, not a claim that Ariatrading is universally production-ready. The repository contains the execution path and safety policy; activation remains external to source control and must be performed on the operator's MT5 host.

## Next milestone

### Production expansion — only after verified Stage 1 evidence
- Observe long-duration live behavior with strict operational review.
- Add additional symbols only through explicit policy changes and fresh verification evidence.
- Keep strategy changes separate from execution-policy changes.
