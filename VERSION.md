# Ariatrading Version

Current version: **0.4.0**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Current milestone — 0.4.0

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Confirmed-swing market structure is available.
- Fake-breakout classification is integrated into the sequence engine.
- Multi-timeframe context and setup scoring are available.
- Automated test workflow has been added.
- Next milestone: true timestamp-aligned MTF historical backtesting and validation.
