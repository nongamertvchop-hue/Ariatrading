# Guarded MT5 runtime runbook

## DEMO first

Use the dedicated guarded entrypoint:

```bash
python -m live.live_entry --mode DEMO --symbols EURUSD,GBPUSD,USDJPY --timeframe 15m
```

The default is DEMO. The runtime requires the connected MT5 account to actually be a demo account. It also checks trading permissions, execution-journal state, spread, tick freshness, candle freshness, position caps, daily drawdown, and broker/local clock skew.

## Emergency stop

Create the configured kill-switch file (default `data/KILL_SWITCH`):

```bash
mkdir -p data && printf '%s\n' 'operator emergency stop' > data/KILL_SWITCH
```

This blocks **new entries**. It does not blindly liquidate existing positions. Existing positions must be reconciled with the broker before any restart.

To release the switch after investigation, delete the file explicitly:

```bash
rm -f data/KILL_SWITCH
```

## LIVE is intentionally two-step

1. Verify the connected MT5 account is a real, trade-enabled account.
2. Set `ARIATRADING_ENABLE_LIVE=I_UNDERSTAND_REAL_ORDERS` in the runtime environment.
3. Start the guarded entrypoint with `--mode LIVE`.

A copied command cannot silently upgrade DEMO to LIVE because account-mode reconciliation and the explicit environment opt-in are both checked.

## Restart policy

Never auto-retry a run when `data/execution_journal.json` contains `RESERVED`, `SUBMITTED`, or `AMBIGUOUS` intents. Reconcile those intents against MT5 positions/deals first. The runtime is deliberately fail-closed because a transport timeout can happen after the broker accepted an order.

## Operational evidence

The runtime writes a latest heartbeat to `data/runtime_heartbeat.json` and append-only JSONL events to `data/runtime_events.jsonl`. Keep these files with the execution journal for incident review and post-trade analysis.

## Release path

`ALERT_ONLY` -> DEMO -> DEMO soak/shadow comparison -> small staged LIVE exposure -> broader LIVE only after the preceding stage is stable.

This repository does not define a safe point at which a profit target overrides the safety gates. Safety gates remain authoritative even when the strategy appears profitable.
