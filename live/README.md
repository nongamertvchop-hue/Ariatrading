# Live boundary

This directory is the target home for the smallest safety-critical runtime.

## Current runtime

`paper_runtime.py` is the active automation runtime for the current phase. It
polls the existing `RealtimeMonitor`, processes only newly closed candles, and
drives the existing `PaperSessionRunner`. It is simulation-only and cannot send
MT5 orders.

Allowed responsibilities:

- Running the closed-candle realtime loop.
- Exposing runtime health and paper-account state.
- Validating broker contracts and normalized broker snapshots when an execution
  adapter is eventually supplied.
- Position reconciliation and execution recovery.
- System/risk gates and paper-session orchestration.
- Loading an already-trained, explicitly versioned model artifact.

The live boundary must not train models, run backtests, tune features, or
silently fall back to research logic. Broker interaction must remain behind an
adapter, and all execution paths must fail closed on ambiguity.

## Promotion boundary

The supported progression is:

```text
RESEARCH
   -> REALTIME OBSERVATION
   -> AUTOMATIC PAPER
   -> LONG-RUN PAPER VALIDATION
   -> MT5 DEMO ADAPTER
   -> DEMO VALIDATION
   -> only after evidence: consider live execution
```

`ExecutionMode.DEMO` is intentionally rejected until a real MT5 execution
adapter exists. This prevents an operational flag from accidentally turning a
paper process into a broker process.

The existing `strategy/` modules are not moved in this change because doing so
would create a large, hard-to-audit import migration while the test suite is
already being repaired. Migration should happen module-by-module with tests
remaining green after every move.
