# Ariatrading — Real-Money Execution Stage 1

## Status

Stage 1 is implemented in source control as a deliberately narrow real-money execution boundary. It is **not armed by the repository defaults** and no broker secret is committed.

The execution path uses the same existing strategy/risk boundary as DEMO, then applies an additional Stage 1 production policy before the MT5 broker boundary.

## Stage 1 hard limits

| Control | Stage 1 rule |
|---|---|
| Execution mode | `LIVE` only |
| Account | Exact `login` + `server` allowlist |
| Symbols | Exactly 1 explicitly allow-listed symbol |
| Risk per trade | <= 0.25% of equity |
| Daily equity drawdown | <= 1% |
| Spread | <= 20 points |
| Tick age | <= 5 seconds |
| Candle input | Completed candles only |
| Stop Loss | Required and direction-consistent |
| Broker validation | `order_check()` before `order_send()` |
| Duplicate protection | Deterministic execution intent journal |
| Unknown broker outcome | `AMBIGUOUS` + reconciliation; no blind retry |
| Position ownership | Strategy magic number |

## Activation

The operator supplies these values on the MT5 execution host, through the host's secret/environment mechanism. They must never be committed to Git.

```text
ARIATRADING_ENABLE_LIVE=I_UNDERSTAND_REAL_ORDERS
ARIATRADING_LIVE_STAGE=1
ARIATRADING_LIVE_ACCOUNT=<REAL_MT5_LOGIN>
ARIATRADING_LIVE_SERVER=<EXACT_MT5_SERVER_NAME>
ARIATRADING_LIVE_SYMBOLS=EURUSD
ARIATRADING_LIVE_MAX_RISK=0.0025
ARIATRADING_LIVE_MAX_DAILY_DD=0.01
ARIATRADING_LIVE_MAX_SPREAD_POINTS=20
ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS=5
```

The canonical hardened runtime is:

```text
python -m live.runtime_cli --mode LIVE --symbols EURUSD --risk 0.0025
```

An alternative hardened entry point is:

```text
python -m live.live_runtime_cli --mode LIVE --symbols EURUSD --risk 0.0025
```

`live/runner.py` is also constrained by the same Stage 1 account, symbol and risk policy so it cannot bypass the production boundary.

## What this release does not do

It does not create or store broker credentials, identify the operator's private account, or remotely start a real MT5 terminal. Those actions require the operator's execution host and broker session.

Passing CI or the release gate is an engineering verification result only. It is not a profitability claim and does not remove market, broker, liquidity, slippage, or infrastructure risk.

## Rollback / immediate disable

Remove the LIVE environment opt-in or set `ARIATRADING_LIVE_STAGE=0`, then stop the runtime process. The next startup fails closed before the execution loop begins. Never attempt to recover an `AMBIGUOUS` execution by resubmitting the same intent; broker-side evidence must reconcile it first.
