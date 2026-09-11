# 0.17.2

- Hardened MT5 timestamp handling in the realtime feed guard.
- Routed MT5 `/api/strategy` requests through the canonical realtime feed-integrity boundary.
- Added regression coverage for epoch timestamps, duplicates, and out-of-order bars.
- Kept broker execution unchanged; supported runtime remains paper/demo only.
