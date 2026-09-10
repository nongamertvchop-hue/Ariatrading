# Ariatrading — 50-Point Real-Trading Readiness Program

**Target:** a system that can *safely* reach real MT5 execution after verification, not a system that blindly enables LIVE.

A score of 50/50 is not permission to trade money. The release gate additionally requires green automated tests, verified broker behavior on DEMO, operational monitoring, and explicit operator approval.

| # | Workstream | Status in this pass |
|---|---|---|
| 1 | Explicit LIVE opt-in | Present and retained |
| 2 | DEMO/REAL account reconciliation | Present and retained |
| 3 | MT5 trade-permission check | Present and retained |
| 4 | Terminal connection health | Hardened runtime gate |
| 5 | Symbol availability/select | Present in executor |
| 6 | Broker contract validation | Present; runtime reuses contract |
| 7 | Tick freshness | Hardened runtime gate |
| 8 | Spread ceiling | Hardened runtime gate |
| 9 | Completed-candle-only strategy input | Present |
| 10 | Future timestamp rejection | Hardened |
| 11 | Broker history failure handling | Fail-closed in runner |
| 12 | Candle freshness check | Hardened runtime gate |
| 13 | Minimum history requirement | Present in orchestrator |
| 14 | Signal protection gate | Present |
| 15 | Session/market-condition gate | Present |
| 16 | Risk-per-trade contract | Present |
| 17 | Stop-loss direction validation | Present in executor |
| 18 | Broker stop-distance validation | Broker-side check remains authoritative |
| 19 | Volume min/max/step validation | Present |
| 20 | Margin/order preflight | `order_check()` present |
| 21 | Global position cap | New runtime control |
| 22 | Per-symbol position cap | New runtime control |
| 23 | Exposure inventory from owned positions | New runtime control |
| 24 | Daily realized-loss accounting | Present in runner |
| 25 | Daily equity drawdown circuit breaker | Present and persisted |
| 26 | Persistent idempotency journal | Present |
| 27 | Atomic journal persistence | Present |
| 28 | Ambiguous outcome quarantine | Present |
| 29 | No blind retry after ambiguity | Present |
| 30 | Broker retcode validation | Present |
| 31 | Position ownership by magic number | Present |
| 32 | Post-start reconciliation of unfinished intents | Runtime preflight gate |
| 33 | Execution confirmation data | Present in `OrderResult` |
| 34 | Close-order preflight | Present |
| 35 | Duplicate-intent suppression | Present |
| 36 | Durable operator kill switch | New |
| 37 | Kill switch integrated as a release gate | New runtime integration |
| 38 | Runtime fail-closed exception boundary | Present |
| 39 | Restart-safe warm-up | Present |
| 40 | Deterministic intent identity | Present |
| 41 | Structured operational logging | Present |
| 42 | Operator notification path | Present via notifier |
| 43 | Local runtime heartbeat/health state | Next integration target; no false claim |
| 44 | Audit/event retention policy | Next integration target; no false claim |
| 45 | Static runtime configuration validation | New |
| 46 | Broker/local clock-skew protection | New |
| 47 | Timezone-aware timestamps | Present across live path |
| 48 | Strategy/backtest parity | Existing project work; must be verified continuously |
| 49 | DEMO soak + shadow comparison | Release requirement |
| 50 | Staged LIVE rollout / emergency rollback procedure | Release requirement |

## What changed now

This branch introduces a single safety-control module (`live/runtime_controls.py`) for configuration validation, clock-skew checks, exposure counting, and a durable operator kill switch. The existing `live/live_runtime.py` is the intended runtime boundary; duplicated polling logic in `live/runner.py` must not remain the long-term architecture.

## Hard release gate

The system must remain in `ALERT_ONLY` or `DEMO` until all verification is green. LIVE requires both the existing explicit environment opt-in and a verified MT5 real account. Any unreadable journal, stale tick, invalid contract, excessive spread, drawdown breach, kill switch, account mismatch, or ambiguous broker outcome must block new execution.
