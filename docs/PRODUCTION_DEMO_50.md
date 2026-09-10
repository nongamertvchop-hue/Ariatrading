# Ariatrading — Production-Grade DEMO 50% Milestone

Status: IN PROGRESS
Target: production-like DEMO operation without enabling real-money broker execution.

## Objective

Reach the first 50% engineering milestone for a production trading system while keeping the broker execution boundary fail-closed. This milestone is about operational reliability, not profitability and not authorization to trade real money.

## Scope completed / being certified

- Canonical two-setup strategy: LONG at support and SHORT at resistance.
- Chronological backtest/realtime/paper parity.
- Look-ahead/data-leakage protections at the strategy/research boundaries.
- Real MT5 market-data bridge for read-only live price/candle observation.
- Paper/DEMO execution simulation with persistent order state and recovery.
- Broker-contract validation for symbol, price precision and volume constraints.
- Account/session identity checks in the execution adapter.
- Daily drawdown circuit-breaker and stale-tick/spread guards in the runtime.
- Durable execution journal and explicit AMBIGUOUS state; no blind retry after an unknown broker outcome.
- Durable Bodyguard telemetry with sanitized incident events.
- Operational Webaria dashboards for market, runtime and Bodyguard state.
- Fix Error records for regressions, with tests required before an incident can be considered resolved.
- CI coverage for Python, Worker/Webaria JavaScript syntax/tests and polyglot validators.
- Deterministic 10,000-bar paper soak, crash/restart recovery and historical shadow validation remain release evidence.

## Explicit 50% boundary

The milestone does **not** activate, arm, or authorize automated real-money orders. In particular, this document must never be interpreted as permission to remove execution guards, bypass the release gate, or expose broker credentials through Webaria/Cloudflare.

The supported operational target for this milestone is:

```text
MT5 live market data
        |
        v
strategy -> risk -> paper/demo execution
        |
        +--> durable journal
        +--> recovery
        +--> Bodyguard telemetry
        +--> Webaria operational console
```

## Remaining work before any separate execution review

1. Verify all CI jobs on the current revision are green.
2. Run sustained DEMO/soak sessions against live MT5 market data.
3. Measure signal latency, missed bars, duplicate events and restart recovery.
4. Verify broker contract fixtures for every supported symbol.
5. Expand failure-injection coverage for disconnects, timeouts, stale data and corrupted persistence.
6. Review operational alerting and incident retention.
7. Produce an independent execution-risk review before considering any future broker-execution promotion.

## Acceptance rule

A green test suite is necessary but not sufficient. No claim of profitability, robustness in unseen markets, or real-money readiness may be inferred from this milestone. Any future execution promotion must remain a separately reviewed boundary with independent controls.
