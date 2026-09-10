# LIVE Safety Layers

This document maps the next 20 hardening items to concrete implementation layers. It is a release-engineering checklist, not proof that LIVE is approved.

| # | Control | Implementation / evidence |
|---|---|---|
| 1 | Single runtime enforcement | `live/live_runtime.py` is the guarded control plane; legacy loops must not be treated as production entrypoints. |
| 2 | Preflight every cycle | account, kill switch, reconciliation, circuit breaker and exposure checks execute before strategy delegation. |
| 3 | Position reconciliation | `live/position_reconciliation.py` compares active journal intents with broker-owned positions. |
| 4 | Partial-fill handling | broker result and observed position state are kept separate; ambiguous state requires reconciliation instead of retry. |
| 5 | Stale position detection | reconciliation reports missing broker matches as blocking mismatch. |
| 6 | Duplicate position protection | journal identity plus one-to-one reconciliation prevent blind duplicate submission. |
| 7 | Exposure by direction | `live/exposure.py` aggregates BUY/SELL volume independently. |
| 8 | Risk aggregation | `live/exposure.py` aggregates stop-defined cash risk and provides a fail-closed budget check. |
| 9 | Equity vs balance protection | account equity is the primary circuit-breaker/risk basis; non-finite/invalid equity blocks. |
| 10 | Floating drawdown guard | `DailyCircuitBreaker` compares current equity with persisted daily starting equity. |
| 11 | Spread shock protection | runtime blocks when broker spread exceeds configured points. |
| 12 | Market-data gap detection | `live/data_quality.py` rejects non-monotonic timestamps and gaps larger than one timeframe. |
| 13 | Execution latency measurement | execution telemetry must record submission-to-observation timing before LIVE approval. |
| 14 | Broker reject classification | `live/execution_outcome.py` classifies known rejection/transient codes and defaults unknown outcomes to AMBIGUOUS. |
| 15 | Kill-switch audit | durable kill-switch events are emitted through runtime telemetry. |
| 16 | Runtime health contract | `live/runtime_health.py` exposes HEALTHY/DEGRADED/BLOCKED/ERROR states. |
| 17 | Strategy/execution isolation | runtime delegates the decision; broker calls remain inside `MT5LiveExecutor` and the execution guard. |
| 18 | Backtest/paper/live contract | existing paper/backtest infrastructure remains the strategy validation boundary; LIVE requires separate operational evidence. |
| 19 | DEMO soak evidence | `live/release_evidence.py` stores explicit, timestamped, referenced operator evidence; no synthetic pass is generated. |
| 20 | LIVE release ceremony | release gate remains 1..50 explicit-true; staged LIVE, rollback drill and approval evidence must be supplied externally. |

## Release rule

Code existence is not equivalent to operational proof. A readiness item remains false until its required test, demo-soak, shadow comparison, broker evidence, or operator approval is actually recorded.

In particular, this branch must not be merged to claim LIVE readiness while GitHub Actions has no verified passing run and while DEMO soak / staged-live evidence is absent.
