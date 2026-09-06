# Ariatrading Version

Current version: **0.5.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.5.0

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure is available.
- Fake-breakout classification is integrated into the sequence engine.
- Multi-timeframe context and setup scoring are available.
- Automated test workflow has been added.
- Realtime monitoring now has a feed interface plus an MT5 market-data adapter.
- Realtime evaluation uses closed candles only; the currently forming candle is excluded.
- MT5 integration is read-only at this stage; no order execution is implemented.
- Next milestone: timestamp-aligned historical MTF validation and realistic execution simulation.
