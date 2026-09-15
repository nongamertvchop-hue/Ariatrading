# Ariatrading A→B→C→D Upgrade Contract

This document records the integrated engineering pass for Ariatrading. The runtime remains **PAPER/DEMO only**.

## A — Architecture audit

Backtest, Realtime Replay, and Paper Runtime must consume the same decision semantics. The parity certificate therefore fails closed when a source stream contains duplicate timestamps, non-monotonic timestamps, or decisions missing from the other stream.

The certificate validates ordering and uniqueness before timestamp-keyed comparison, reports both directions of missing decisions, preserves chronological comparison, and keeps deterministic fingerprints and paper-runtime consumption checks.

## B — Paper execution hardening

Paper execution remains a state machine, not a profit simulator:

- closed candles only;
- deterministic next-bar signal consumption;
- explicit stop/target semantics;
- persistent checkpoint and append-only history;
- restart recovery fails closed on unresolved execution ambiguity;
- broker symbol/price/volume contracts are validated before execution boundaries;
- browser state is observational and cannot become authoritative execution state.

## C — Dashboard contract

The Webaria dashboard remains an observability surface. It must expose authoritative runtime lifecycle, heartbeat/checkpoint health, account metrics, position/execution state, events, equity history, recovery status, export, and explicit PAPER/DEMO labeling.

The browser cannot turn WAIT into an order, alter authoritative account state, or bypass release gates.

## D — Research contract

Research remains chronology-safe and reproducible:

- one canonical strategy boundary;
- chronological train/test separation;
- causal labels using only candles after the signal;
- no higher-timeframe look-ahead;
- reproducible data/config/code fingerprints;
- baseline versus filtered comparison;
- robustness and stability diagnostics;
- explicit failure reporting;
- no automatic promotion from research evidence to execution.

ML/DL may filter or score existing LONG/SHORT setups. They cannot create a third entry direction.

## Release acceptance

Relevant Python and JavaScript tests must pass in CI and the final paper release gate must remain green. A green gate is engineering evidence, not a profitability claim and not permission for real-money trading.
