# Live boundary

This directory is the target home for the smallest safety-critical runtime.

Allowed responsibilities:

- Validating broker contracts and normalized broker snapshots.
- Position reconciliation and execution recovery.
- System/risk gates and paper/demo/live-session orchestration.
- Loading an already-trained, explicitly versioned model artifact.

Execution modes are explicit:

- `ALERT_ONLY`: signal/monitoring only; no broker orders.
- `DEMO`: broker execution against an MT5 demo account.
- `LIVE`: broker execution against an MT5 real account.

`LIVE` is not a research shortcut. It uses the same strategy-to-risk boundary as
`DEMO`, including broker contract validation, mandatory Stop Loss, risk sizing,
execution idempotency, and fail-closed handling of ambiguous broker responses.
It must be selected explicitly and is not the process default.

The live boundary must not train models, run backtests, tune features, or
silently fall back to research logic. Broker interaction must remain behind an
adapter, and all execution paths must fail closed on ambiguity.

MT5 connectivity is provided by `live/mt5_executor.py` for order execution and
`mt5/AriatradingBridge.mq5` for authenticated broker-market ingestion into the
Worker. The MQL5 bridge remains a feed adapter rather than a second strategy
engine, so signal logic stays centralized and auditable.

The existing `strategy/` modules are not moved in this change because doing so
would create a large, hard-to-audit import migration while the test suite is
already being repaired. Migration should happen module-by-module with tests
remaining green after every move.
