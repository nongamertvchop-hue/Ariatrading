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

Target: complete the 10-item development plan while preserving the two-setup-only philosophy and fail-closed safety model.

### Phase 1 — Research Foundation (in progress)
1. **Signal Event ID + Deduplication** ← current focus
   - Deterministic `signal_id` on every `EngineSignal`
   - `SignalRegistry` for in-memory deduplication
   - Journal and realtime paths updated to carry the ID
2. Historical Signal Replay in Webaria
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

- Added `strategy/signal_id.py` with `make_signal_id()` and `SignalRegistry`
- Extended `EngineSignal` with optional `signal_id` field
- `evaluate_long` / `evaluate_short` now accept `symbol` and attach a deterministic ID

## Previous milestone — 0.14.3

(See git history for full 0.14.3 notes)
