# Ariatrading Version

Current version: **0.15.0-dev** (branch `feat/roadmap-0.15.0-full`)

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Continuation protocol

At the start of a new chat, read this file and `README.md` first, then inspect the latest commits before changing code. Continue from the current version instead of recreating earlier work.

## Active Roadmap — 0.15.0

### Phase 1 — Research Foundation (in progress)
1. **Signal Event ID + Deduplication** — largely complete (Python + Worker event_id already present)
2. **Historical Signal Replay / History in Webaria** — started
   - Signal Advisor now keeps browser-local signal history keyed by `event_id`
   - Deduplicates repeated polls of the same closed-bar decision
3. Outcome Labeling for Paper Signals
4. Signal Quality Report Dashboard
5. MTF Filtered vs Unfiltered comparison

### Phase 2 — Boundary & Execution
6. Move safety modules into `live/` boundary
7. Demo Auto-Trading (MT5 Demo account)
8. Full Live Execution Adapter (read-write, fail-closed)

### Phase 3 — Hardening
9. Shared Parity Contract (Python ↔ Worker)
10. Freeze Strategy Spec + 1.0.0 release

## Changes in this branch so far

- `strategy/signal_id.py` + registry
- `EngineSignal.signal_id`, journal + realtime integration
- RealtimeMonitor registers signals and exposes `is_new_signal`
- Webaria Signal Advisor:
  - Signal History panel (localStorage, event_id dedupe)
  - Live price polling every 8s
  - Stronger chart (zone band, live price line, last-candle emphasis)
  - Shows Event ID in UI
- Unit tests for signal ID generation/registry

## Note on live site

Production Worker at `https://ariatrading.nongamertvchop.workers.dev` deploys from **main** only.
This branch must be merged (or manually deployed) before UI changes appear on the public site.
