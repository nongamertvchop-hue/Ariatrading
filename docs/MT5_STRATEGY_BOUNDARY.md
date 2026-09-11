# MT5 → Strategy boundary

The canonical Worker `/api/strategy` route treats `source: "mt5"` as a realtime market-data input and applies the same closed-candle feed-integrity guard used by the realtime signal path before strategy evaluation.

The guard validates OHLC geometry, strict chronology, duplicate timestamps, timeframe-grid alignment, future timestamps, and staleness. MT5 Unix epoch seconds and milliseconds are normalized by the guard.

The duplicate cursor is advanced only after a successful strategy evaluation. Duplicate or older closed bars return `409` with `signal: "WAIT"` and `state: "NO_UPDATE"`; other feed-integrity failures fail closed with `503`.

This boundary does not place broker orders. The project remains PAPER/DEMO-only for supported runtime and release-gate purposes.
