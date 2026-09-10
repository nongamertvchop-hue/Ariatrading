# LIVE Stage 3 — Production Gate

Stage 3 is the third controlled LIVE boundary for Ariatrading. It is intentionally a **reliability promotion, not a risk-budget increase**.

## Hard limits

| Control | Stage 3 ceiling |
|---|---:|
| Symbols | 2 unique allow-listed symbols |
| Risk per trade | 0.50% |
| Daily drawdown | 2.00% |
| Spread | 30 points |
| Tick age | 10 seconds |
| Heartbeat age | 15 seconds |
| Open positions | 2 |
| Orders / rolling hour | 4 |

A requested value above any ceiling is rejected. Non-finite values are rejected as well.

## Required operational controls

Before a Stage 3 policy can be loaded:

1. LIVE opt-in must be explicit.
2. `ARIATRADING_LIVE_STAGE=3` must be set.
3. Exact MT5 login and server identity must be configured.
4. Symbols must be explicitly allow-listed.
5. `ARIATRADING_LIVE_KILL_SWITCH` must be explicitly set to `OFF`.
6. The heartbeat must be fresh.
7. Broker/state reconciliation must have succeeded.
8. The startup self-test must have passed.
9. Market spread and tick freshness must be inside policy.
10. Per-trade risk and daily drawdown must be inside policy.

Any failed condition is fail-closed: no order should proceed.

## Important boundary

`live/production_stage3.py` is a policy gate. It does **not** create an MT5 connection and does **not** call `order_send()`.

The repository's supported runtime remains PAPER/DEMO. CI must never send a real broker order. A production execution host requires a separately reviewed deployment, credentials supplied outside Git, broker/account eligibility checks, monitoring, and an explicit operational release decision.

## Activation contract

The environment interface is intentionally explicit:

```text
ARIATRADING_ENABLE_LIVE=I_UNDERSTAND_REAL_ORDERS
ARIATRADING_LIVE_STAGE=3
ARIATRADING_LIVE_ACCOUNT=<operator-supplied-login>
ARIATRADING_LIVE_SERVER=<operator-supplied-server>
ARIATRADING_LIVE_SYMBOLS=EURUSD,GBPUSD
ARIATRADING_LIVE_MAX_RISK=0.005
ARIATRADING_LIVE_MAX_DAILY_DD=0.02
ARIATRADING_LIVE_MAX_SPREAD_POINTS=30
ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS=10
ARIATRADING_LIVE_KILL_SWITCH=OFF
```

Do not commit credentials or private account data. The kill switch defaults to `ON` whenever the variable is absent.
