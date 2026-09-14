# Ariatrading A→B→C→D Upgrade Contract

This document records the next integrated engineering pass for Ariatrading. The runtime remains **PAPER/DEMO only**.

## A — Architecture audit

The three-way parity certificate is a critical boundary because Backtest, Realtime Replay, and Paper Runtime must consume the same decision semantics.

The audit found and fixed a fail-open comparison hazard: decision records were first converted to dictionaries keyed by timestamp. A duplicate timestamp could therefore overwrite an earlier record, and a Backtest-only decision could remain unnoticed when Realtime had a different set of timestamps.

The patched certificate now:

1. rejects duplicate decision timestamps;
2. rejects non-monotonic decision order;
3. reports Backtest decisions missing from Realtime;
4. reports Realtime decisions missing from Backtest;
5. compares records in their original chronological order;
6. keeps the existing fingerprint and Paper Runtime consumption checks.

Regression tests cover duplicate Realtime timestamps and an unmatched Backtest decision.

## B — Paper execution hardening

Paper execution is treated as a state machine, not as a profit simulator. The release contract therefore remains:

- closed candles only;
- deterministic next-bar signal consumption;
- explicit stop/target semantics;
- persistent checkpoint and append-only history;
- restart recovery must fail closed on unresolved execution ambiguity;
- broker symbol/price/volume contracts are validated before any execution boundary;
- browser state is observational and cannot become authoritative execution state.

The existing soak, failure-injection, process-death recovery, and historical-shadow gates remain mandatory. New changes must preserve these invariants rather than bypass them.

## C — Dashboard contract

The Webaria dashboard is an observability surface. It must show the authoritative runtime state without inventing a second trading state.

Required dashboard facts:

- lifecycle: OPEN / HALT;
- heartbeat and checkpoint health;
- balance, equity, P/L and drawdown;
- current position and execution state;
- event stream and alerts;
- equity history;
- recovery status;
- exportable snapshot;
- explicit indication that the environment is PAPER/DEMO only.

The browser must never be able to turn a WAIT decision into an order, alter authoritative account state, or bypass the release gate.

## D — Research contract

Research remains hypothesis-driven and chronology-safe. Every experiment should preserve:

- one canonical strategy boundary;
- chronological train/test separation;
- causal labels using only candles after the signal;
- no look-ahead through higher-timeframe alignment;
- reproducible configuration/data/code fingerprints;
- baseline versus filtered comparison;
- robustness and stability diagnostics;
- explicit failure reporting;
- no automatic promotion from research evidence to execution.

ML/DL may filter or score existing LONG/SHORT setups. They cannot create a third entry direction.

## Release acceptance

A change is acceptable only when the relevant Python and JavaScript tests pass in CI and the final paper release gate remains green. A green gate is engineering evidence, not a profitability claim and not permission for real-money trading.
