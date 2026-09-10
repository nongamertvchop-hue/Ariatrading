# Ariatrading — Real-Money Execution Stage 2

## Purpose

Stage 2 is the next controlled live-execution tier after Stage 1. It widens the deployment envelope without changing the trading strategy or removing the broker/execution safety gates.

## Hard limits

| Control | Stage 2 |
|---|---|
| Execution mode | `LIVE` only |
| Account identity | Exact MT5 `login` + `server` |
| Symbols | 1–2 explicitly allow-listed symbols |
| Risk per trade | `<= 0.50%` of equity |
| Daily equity drawdown | `<= 2%` |
| Spread | `<= 30` points |
| Broker tick age | `<= 10` seconds |
| Candle source | Completed candles only |
| Stop Loss | Required and direction-consistent |
| Broker validation | `order_check()` before `order_send()` |
| Execution identity | Deterministic journal / intent ID |
| Unknown broker outcome | `AMBIGUOUS`, reconcile before any retry |
| Position ownership | Strategy magic number |

The hard ceilings live in `live/production_stage2.py`; environment variables cannot increase them.

## Explicit activation

The execution host supplies the actual MT5 credentials and exact account identity outside Git. The following values are illustrative configuration names only:

```text
ARIATRADING_ENABLE_LIVE=I_UNDERSTAND_REAL_ORDERS
ARIATRADING_LIVE_STAGE=2
ARIATRADING_LIVE_ACCOUNT=<REAL_MT5_LOGIN>
ARIATRADING_LIVE_SERVER=<EXACT_MT5_SERVER_NAME>
ARIATRADING_LIVE_SYMBOLS=EURUSD,GBPUSD
ARIATRADING_LIVE_MAX_RISK=0.005
ARIATRADING_LIVE_MAX_DAILY_DD=0.02
ARIATRADING_LIVE_MAX_SPREAD_POINTS=30
ARIATRADING_LIVE_MAX_TICK_AGE_SECONDS=10
```

Canonical hardened runtime:

```text
python -m live.runtime_cli --mode LIVE --symbols EURUSD,GBPUSD --risk 0.005
```

The alternative hardened CLI accepts the same Stage 2 environment:

```text
python -m live.live_runtime_cli --mode LIVE --symbols EURUSD,GBPUSD --risk 0.005
```

## Failure behavior

Missing stage arm, account mismatch, malformed configuration, stale data, abnormal spread, invalid broker contract, journal corruption, unresolved execution outcome, or disabled MT5 trading permission blocks the execution path.

## Important boundary

CI and repository tests never send real broker orders. Passing tests verifies code behavior only; it does not establish profitability or remove market, broker, liquidity, slippage, connectivity, or infrastructure risk.

To immediately disable Stage 2, remove the LIVE opt-in or set `ARIATRADING_LIVE_STAGE=0`, then stop the runtime process. An `AMBIGUOUS` intent must be reconciled from broker evidence before any retry.
