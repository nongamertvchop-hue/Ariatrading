# Live boundary

This directory is the target home for the smallest safety-critical runtime.

Allowed responsibilities:

- Validating broker contracts and normalized broker snapshots.
- Position reconciliation and execution recovery.
- System/risk gates and paper-session orchestration.
- Loading an already-trained, explicitly versioned model artifact.

The live boundary must not train models, run backtests, tune features, or
silently fall back to research logic. Broker interaction must remain behind an
adapter, and all execution paths must fail closed on ambiguity.

The existing `strategy/` modules are not moved in this change because doing so
would create a large, hard-to-audit import migration while the test suite is
already being repaired. Migration should happen module-by-module with tests
remaining green after every move.
