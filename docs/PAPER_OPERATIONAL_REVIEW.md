# ARIA Paper Runtime — Final Security & Operational Review

Status: paper/demo only. This review is a release gate for the research runtime; it is not authorization for real-money execution.

## Safety boundary

- Real broker order APIs are not used by the Paper Runtime Dashboard.
- MT5 integration remains read-only market data.
- Strategy direction remains limited to the existing LONG / SHORT / WAIT engine.
- Ambiguous execution outcomes never become a filled position automatically.
- No retry path may submit the same logical order with a new identity.

## Crash / restart recovery

- Runtime state is written with an atomic temporary-file + replace checkpoint on the Python side.
- Browser state is stored as a versioned local checkpoint; corrupted or unsupported state fails closed instead of being silently reset.
- A pending/unknown execution remains HALT after restart because there is no external broker source of truth in paper mode.
- Completed bars use deterministic timestamp ordering and duplicate suppression.
- Recovery restores account balance, realized/unrealized P/L, peak equity, drawdown, trades, open position, exit levels, and last processed bar.

## P/L, equity and drawdown

- Realized P/L updates only when a paper position closes.
- Unrealized P/L is marked to the latest completed candle close.
- Equity = balance + unrealized P/L.
- Peak equity is monotonic within a session/checkpoint.
- Drawdown = max(0, peak equity - equity).
- Drawdown percentage is calculated from peak equity and is persisted with the account state.

## Failure injection matrix

| Failure | Expected behavior |
|---|---|
| Disconnect before submit | HALT; no position |
| Timeout after acceptance | HALT; pending order retained; no assumed fill |
| Rejection | REJECTED; no position |
| Partial fill | HALT; unresolved execution requires reconciliation |
| Broker position disappearance | HALT on reconciliation cycle |
| Checkpoint corruption | HALT; corrupt checkpoint is not overwritten |
| Duplicate candle | NO_UPDATE; no second decision |
| Out-of-order candle | HALT |

## Replay / soak gate

- A deterministic 10,000-bar replay is available in Python and from the dashboard.
- The replay contains both long and short exit paths.
- The same deterministic input is expected to produce the same trade count, final balance/equity, and maximum drawdown on repeated runs.
- Randomness is not required for the soak gate, so failures are reproducible.

## Operational controls

- Start/stop/recover/reset controls are explicit.
- Current lifecycle, heartbeat, checkpoint status, P/L, equity, drawdown, position, failure mode, and runtime events are visible on the dashboard.
- Snapshot export is provided for offline research review.
- Failure mode is explicit and does not silently enable a different execution path.

## Release interpretation

Passing these tests demonstrates engineering correctness for the paper/demo boundary under the tested scenarios. It does **not** prove profitability, future performance, or suitability for real-money use.
