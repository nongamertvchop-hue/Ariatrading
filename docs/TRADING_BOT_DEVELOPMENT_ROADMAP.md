# Ariatrading — Trading Bot Development Roadmap

## Purpose

This document defines the engineering target for Ariatrading: a production-oriented automated trading system built around real broker market data, explicit strategy rules, risk controls, execution safety, monitoring, testing, and continuous evaluation.

A trading bot is not just a strategy that produces BUY/SELL signals. A robust system must cover the full lifecycle from market data ingestion to signal generation, risk approval, order execution, broker reconciliation, monitoring, and post-trade analysis.

## What a trading bot is

A trading bot (automated/algorithmic trading system) is software that follows predefined rules or models to analyze market information and, when permitted by its controls, generate and/or execute trading decisions. Industry trading-system architectures commonly separate market data, strategy development, execution, risk management, analytics, and operational monitoring.

Algorithmic trading does not remove the need for human oversight. Production systems need testing, monitoring, risk limits, and mechanisms that stop abnormal automated behavior.

## Target system architecture

```text
Broker / MT5
    │
    ├── Market Data Adapter
    │      ├── ticks
    │      ├── bid/ask
    │      └── OHLC candles
    │
    ▼
Data Validation + Normalization
    │
    ▼
Market State / Feature Layer
    │
    ▼
Strategy Engine
    │  ├── LONG setup
    │  ├── SHORT setup
    │  ├── WAIT
    │  └── fake-breakout protection
    │
    ▼
Risk Engine
    │  ├── position sizing
    │  ├── stop-loss / take-profit
    │  ├── spread / slippage limits
    │  ├── exposure limits
    │  └── daily loss / drawdown limits
    │
    ▼
Execution Gate
    │  ├── account validation
    │  ├── broker contract validation
    │  ├── order_check
    │  └── idempotency
    │
    ▼
MT5 Execution Adapter
    │
    ▼
Broker
    │
    ├── execution result
    └── position/deal state
          │
          ▼
Reconciliation + Journal
          │
          ├── monitoring
          ├── alerts
          ├── performance analytics
          └── research / backtesting feedback
```

## Systems that should exist

### 1. Market Data System

- MT5 broker feed as the authoritative execution-market source.
- Tick and candle ingestion.
- Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1D.
- Timestamp normalization and timezone discipline.
- OHLC validation.
- Duplicate/out-of-order detection.
- Freshness/heartbeat checks.
- Data-quality status visible to the operator.

### 2. Strategy Engine

- Strategy logic must be independent from broker credentials and execution code.
- Explicit LONG / SHORT / WAIT states.
- Completed-candle-only evaluation to prevent look-ahead bias.
- Support/resistance and trend logic for the current two-move strategy.
- Fake-breakout / stop-hunt protection.
- Multi-timeframe context where useful.
- Strategy versioning so historical results remain reproducible.

### 3. Signal Layer

Every signal should contain enough information to reproduce why it happened:

- symbol
- timeframe
- candle/bar timestamp
- direction
- setup type
- entry reference
- stop-loss
- take-profit
- confidence/quality metadata where applicable
- strategy version
- rejection/protection reason when WAIT

A signal must not directly place an order.

### 4. Risk Management System

Risk must be a hard gate before execution.

Required controls:

- risk-per-trade sizing
- broker volume min/max/step validation
- maximum spread
- maximum slippage/deviation
- stop-loss validation
- take-profit validation
- maximum simultaneous exposure
- per-symbol exposure limits
- daily realized-loss limit
- daily equity drawdown circuit breaker
- account permission checks
- fail-closed behavior on missing/invalid data

### 5. Execution System

Separate execution from strategy.

Required capabilities:

- DEMO and LIVE modes.
- Account-mode validation.
- MT5 connection health checks.
- Symbol visibility and contract validation.
- `order_check()` before `order_send()`.
- Explicit handling of broker retcodes.
- Timeout/transport ambiguity handling.
- No blind retry after an ambiguous broker response.
- Position ownership through strategy magic number.
- Broker-side reconciliation after uncertain execution.

### 6. Order / Position Management

The bot needs to understand the complete lifecycle of a position:

```text
SIGNAL
  ↓
RISK APPROVED
  ↓
ORDER CREATED
  ↓
ORDER CHECKED
  ↓
ORDER SENT
  ↓
FILLED / REJECTED / AMBIGUOUS
  ↓
POSITION OPEN
  ↓
MONITOR
  ↓
EXIT
  ↓
RECONCILE
  ↓
PERFORMANCE RECORD
```

It must distinguish between an order request, broker execution, and resulting position. These are not interchangeable states.

### 7. Idempotency and Recovery

- Deterministic execution intent IDs.
- Persistent execution journal.
- Cross-process serialization.
- RESERVED / SUBMITTED / SUCCEEDED / FAILED / AMBIGUOUS states.
- AMBIGUOUS must never automatically retry.
- Startup reconciliation against broker evidence.
- Runtime must refuse new execution while unresolved intents remain.
- Restart must not replay an old completed signal.

### 8. Backtesting System

Backtesting is required before trusting a strategy with forward execution.

The backtester should support:

- historical OHLC data
- spread assumptions
- slippage assumptions
- commissions/swaps where applicable
- realistic execution rules
- multiple timeframes
- walk-forward evaluation
- out-of-sample testing
- parameter/version tracking
- trade-by-trade logs
- equity curve and drawdown

Critical rule: no look-ahead bias or data leakage.

### 9. Paper / Demo Trading System

Before LIVE:

```text
Backtest
   ↓
Out-of-sample
   ↓
Paper / Demo
   ↓
Forward validation
   ↓
Small controlled LIVE deployment
```

Paper trading should use the same strategy and risk boundaries as LIVE wherever possible. Only the execution adapter should differ.

### 10. Performance Analytics

Track more than win rate:

- total PnL
- net PnL after costs
- expectancy
- profit factor
- maximum drawdown
- average win/loss
- win/loss distribution
- number of trades
- exposure time
- spread/slippage impact
- performance by symbol
- performance by timeframe
- performance by setup type
- performance by market regime

### 11. Monitoring and Alerting

The operator must be able to see whether the bot is healthy.

Monitor:

- MT5 connection
- market-data freshness
- candle freshness
- spread
- account state
- open positions
- pending/unresolved execution intents
- order rejection rate
- runtime heartbeat
- strategy signal rate
- daily loss/drawdown
- process crashes/restarts

Critical events should produce explicit alerts rather than silent failure.

### 12. Kill Switch / Fail-Safe System

The system must have a hard mechanism to stop new entries when conditions become unsafe.

Examples:

- market feed unavailable
- stale ticks
- account changed
- trading permission lost
- excessive spread
- daily drawdown exceeded
- journal corruption
- unresolved ambiguous execution
- broker connection uncertainty
- abnormal order rejection rate
- runaway signal/order rate

Stopping new entries is preferable to trying to guess through an uncertain broker state.

### 13. Configuration and Secrets

- Broker credentials must never live in strategy source code.
- Production configuration must be explicit and validated at startup.
- DEMO/LIVE mode must be explicit.
- LIVE should have additional account/server identity checks.
- Secrets should come from the deployment environment/secret store.

### 14. Testing System

Required layers:

1. Unit tests — individual strategy/risk/execution functions.
2. Contract tests — MT5 adapter and broker response contracts.
3. Integration tests — feed → strategy → risk → execution boundary.
4. Replay tests — deterministic historical market sequences.
5. Failure-injection tests — timeout, stale data, broker rejection, disconnect, duplicate execution.
6. Regression tests — every production bug gets a regression test.
7. CI — all tests must pass before a production-readiness claim.

### 15. Research / ML Layer

Machine learning should be an optional layer, not a bypass around deterministic risk controls.

Potential future capabilities:

- regime classification
- signal quality scoring
- volatility forecasting
- anomaly detection
- parameter selection
- feature research

ML must be validated with strict time-series splits and leakage controls. It must never override hard risk limits or execution safety gates.

## Ariatrading development targets

### Phase A — Foundation

- [x] Real MT5 market-data bridge architecture
- [x] Candle normalization and validation
- [x] LIVE/DEMO execution boundary
- [x] Account-mode validation
- [x] Execution journal
- [x] Broker order preflight
- [x] Daily circuit breaker
- [x] Runtime freshness/spread gates

### Phase B — Execution hardening

- [ ] Verify MT5 retcode semantics against the installed MetaTrader5 package.
- [ ] Harden filling-mode handling per broker symbol.
- [ ] Add stop-level/freeze-level validation.
- [ ] Add final execution-time slippage guard.
- [ ] Reconcile successful market orders against resulting positions/deals.
- [ ] Add broker/server/account identity allowlist for LIVE.
- [ ] Add connection recovery with explicit fail-closed state.

### Phase C — Strategy robustness

- [ ] Formalize the two-move strategy as versioned rules.
- [ ] Expand fake-breakout protection.
- [ ] Add multi-timeframe context without look-ahead.
- [ ] Build deterministic signal replay tests.
- [ ] Measure strategy performance by setup, timeframe, symbol, and regime.

### Phase D — Backtest and validation

- [ ] Production-grade historical data pipeline.
- [ ] Realistic spread/slippage/commission model.
- [ ] Walk-forward validation.
- [ ] Out-of-sample evaluation.
- [ ] Monte Carlo / robustness analysis where appropriate.
- [ ] Reproducible backtest manifests and strategy versions.

### Phase E — Operations

- [ ] Real-time bot health dashboard.
- [ ] Execution/event timeline.
- [ ] Kill switch UI and backend enforcement.
- [ ] Runtime heartbeat.
- [ ] Alerting for critical failures.
- [ ] Daily/weekly performance reports.
- [ ] Audit trail for all signals, orders, fills, and risk decisions.

### Phase F — Advanced intelligence

- [ ] Regime detection.
- [ ] Signal quality model.
- [ ] Anomaly detection.
- [ ] ML research pipeline with strict time-series validation.
- [ ] Champion/challenger strategy evaluation.
- [ ] Controlled strategy promotion workflow.

## Engineering principles

1. Strategy does not execute orders directly.
2. Risk controls cannot be bypassed by strategy or ML.
3. LIVE must use the same core strategy/risk path as DEMO whenever possible.
4. Unknown broker state means STOP, not RETRY.
5. Only completed candles may generate normal strategy decisions.
6. Every order must be explainable after the fact.
7. Every production bug should become a regression test.
8. Backtest results are evidence, not proof of future profitability.
9. CI/test evidence is required before declaring a subsystem production-ready.
10. Human monitoring remains part of the operational safety model.

## Research basis

The architecture above is synthesized from industry material describing algorithmic trading, market-data systems, execution gateways, pre-/post-trade risk controls, analytics, backtesting, real-time alerts, and testing requirements. CME Group materials explicitly describe algorithmic trading as automated methodologies and emphasize monitoring, prudent controls, testing, and risk functionality. Industry trading-system listings also consistently expose market data, execution, risk management, backtesting, analytics, and monitoring as separate capabilities.

References:

- CME Group — Algorithmic Trading and Market Dynamics: https://www.cmegroup.com/education/files/Algo_and_HFT_Trading_0610.pdf
- CME Group — BrokerTec Algorithmic Trading: https://www.cmegroup.com/tools-information/webhelp/cme-customer-center/Content/brokertec-algo.html
- CME Group — Risk Management Interface overview: https://www.cmegroup.com/globex/files/rmipresentation.pdf
- CME Group — Data and Analytics: https://www.cmegroup.com/market-data.html
