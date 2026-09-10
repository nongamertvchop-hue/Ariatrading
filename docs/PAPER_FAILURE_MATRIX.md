# Paper Trading Runtime — Failure Injection Matrix

This matrix is the runtime contract for ARIA's paper-only execution path.
Every failure must either reconcile to one deterministic state or fail closed.
No failure mode is allowed to invent a second order.

| Failure | Injection | Expected lifecycle | Expected action | Continue? |
|---|---|---|---|---|
| Stale/invalid feed | reject feed batch | HALT | HALT | No |
| Duplicate closed candle | replay same bar | current state | NO_UPDATE | Yes |
| Out-of-order candle | reorder bars | HALT | HALT | No |
| Missing candle | remove a bar | HALT | HALT | No |
| Disconnect before submit | broker disconnected | UNKNOWN | HALT | No |
| Timeout after accept | accept order, lose response | UNKNOWN → OPEN/CLOSED after reconcile | RECONCILE | Yes, only after proof |
| Order rejected | broker returns REJECTED | FLAT | REJECTED | Yes |
| Partial fill | broker fills < requested | HALT | HALT | No |
| Duplicate order | same idempotency/client ID | existing order state | DUPLICATE | Yes |
| Position disappears | broker becomes flat while local is open | HALT | HALT | No |
| Quantity mismatch | broker volume differs beyond contract tolerance | HALT | HALT | No |
| Tampered audit | hash chain or payload mismatch | HALT | HALT | No |
| Missing audit coverage | local order has no latest audit event | HALT | HALT | No |
| Orphan audit event | journal references unknown order | HALT | HALT | No |
| Process crash | terminate between states | UNKNOWN/previous checkpoint | RECOVER | Only after reconciliation |
| Unknown order state | broker returns unsupported status | HALT | HALT | No |
| Corrupt runtime checkpoint | invalid JSON/schema | HALT | HALT | No |
| Symbol/timeframe mismatch | checkpoint differs from runtime | HALT | HALT | No |

## Restart invariant

A restart never resubmits an order merely because the previous process did not
receive a response. The new process restores the order identity, inspects the
paper broker's durable state, reconciles positions, verifies the append-only
audit chain, and only then resumes the candle loop.

## Duplicate invariant

`client_order_id` and `idempotency_key` are deterministic for a closed-candle
signal. Replaying the same candle must return the original logical order state,
not create a second broker order.

## Paper-only invariant

The runtime uses `PaperBrokerSimulator` / browser paper state only. There is no
live broker transport, live account credential, or real-money execution path in
this runtime.
