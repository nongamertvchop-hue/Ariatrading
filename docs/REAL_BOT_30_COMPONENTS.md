# Ariatrading — 30 Components for a Production Trading Bot

## Purpose

This document turns the requested 30-item checklist into an engineering contract for Ariatrading.

Ariatrading is currently a **research + paper/demo system**. The checklist below is therefore a readiness map, not a claim that live-money execution is enabled.

The project is built around **MetaTrader 5 (MT5)** for the intended Forex execution path. Several items in the generic checklist are exchange-oriented concepts and are therefore mapped to the MT5 equivalent or marked optional rather than forced into the core architecture.

## 30-component checklist

| # | Component | Ariatrading mapping | Status | Engineering note |
|---|---|---|---|---|
| 1 | Python | Core strategy/research/runtime language | READY | Primary implementation language. |
| 2 | ccxt | Optional exchange adapter | OPTIONAL | Not required for the MT5-first Forex path; do not duplicate the strategy for another transport. |
| 3 | pandas | Market-data/research dataframe layer | OPTIONAL/RESEARCH | Useful for offline analysis; core strategy can remain lightweight. |
| 4 | TA-Lib | Optional indicator library | OPTIONAL | The current core strategy is price-action based; indicators must not silently create a third setup. |
| 5 | Exchange API | MT5 terminal integration / broker execution adapter | ADAPTER | For MT5, the official Python package communicates with the running MT5 terminal rather than using a generic crypto-exchange REST API. |
| 6 | Testnet | MT5 demo account + paper simulator | READY | Demo/paper is the required pre-live boundary. |
| 7 | API Key / Secret | MT5 account login/session credentials | DESIGN | MT5 authentication is account/server based rather than an exchange API-key pair. |
| 8 | .env | `.env.example` + deployment environment | READY | Secrets/configuration must stay outside strategy source. |
| 9 | IP Whitelist | Broker/provider/network access policy | OPTIONAL | Relevant to providers that expose API IP allowlists; not a universal MT5 requirement. |
| 10 | VPS | Always-on execution host | PLANNED | Required for unattended production runtime. |
| 11 | Ubuntu | Server OS option | OPTIONAL | MT5 Python integration is terminal-based and the official setup is Windows-oriented; do not force Ubuntu if it makes the MT5 terminal path fragile. |
| 12 | systemd | Linux service supervisor | OPTIONAL | Useful when the selected production host is Linux and the execution adapter supports it cleanly. |
| 13 | Docker | Reproducible runtime packaging | PLANNED/OPTIONAL | Good for stateless services and support tooling; MT5 terminal hosting must be validated separately before containerizing. |
| 14 | SQLite | Local state/audit persistence | READY/PRESENT | Existing order state, checkpoints, journals and research persistence should remain authoritative per subsystem. |
| 15 | Redis | Fast cache/queue | OPTIONAL | Add only where measured latency/concurrency requires it; do not use Redis as the sole source of execution truth. |
| 16 | REST API | Control/observability interface | PRESENT/PLANNED | Webaria/Worker already provide browser-facing APIs; production controls must remain fail-closed server-side. |
| 17 | WebSocket | Realtime transport | PRESENT/PLANNED | Realtime market/event streaming can use WebSocket where the chosen provider supports it. |
| 18 | Rate Limit | Provider request throttling | REQUIRED | Must exist at every external-provider boundary with bounded retries and backoff. |
| 19 | OHLCV | Canonical market-data contract | READY | Feed validation already enforces timestamped OHLC integrity; volume semantics are provider-dependent in Forex. |
| 20 | Timeframe | 1m through 1D | READY | Realtime and strategy layers support the requested multi-timeframe path. |
| 21 | Indicator | Derived market features | OPTIONAL | Indicators are contextual tools only; the two core LONG/SHORT setups remain the strategy boundary. |
| 22 | Strategy | LONG / SHORT / WAIT + protection | READY | Strategy is isolated from execution and risk code. |
| 23 | Backtest | Sequential historical evaluation | READY | Includes chronological validation and explicit execution assumptions. |
| 24 | Paper Trading | Deterministic simulation/runtime | READY | Continuous paper runtime, accounting, recovery, and soak testing already exist. |
| 25 | Risk Management | Position/account/trade risk gates | READY | Risk is a hard pre-execution gate and fails closed on invalid state. |
| 26 | Stop Loss / Take Profit | Broker-aware exit planning | READY/DEMO | Risk/exit planning exists; live broker-side execution still requires dedicated final validation. |
| 27 | Position Sizing | Account-aware quantity calculation | READY/DEMO | Includes broker min/max/step contracts and account-level limits. |
| 28 | Order Types | Market/limit/stop and broker semantics | DESIGN/DEMO | Generic OCO semantics must not be assumed across brokers; MT5-specific order/fill rules need explicit contract tests. |
| 29 | Logging & Monitoring | Journals, heartbeats, dashboard, audit | READY | Runtime health, event streams, audit chains, recovery and operational review are already part of the architecture. |
| 30 | Telegram Bot | Critical operator alerts | READY/CONFIGURED | `.env.example` already defines Telegram credentials and notification flags. |

## MT5-specific corrections to the generic checklist

### Exchange API is not the same thing as MT5

For the intended Forex path, the execution adapter should target the official MetaTrader 5 Python integration and a running MT5 terminal. The MT5 integration exposes initialization, account information, market-data access and order-related functions through the terminal connection. It is therefore cleaner to keep `ccxt` optional instead of introducing an unnecessary second execution abstraction into the MT5 path.

### API Key / Secret is not the MT5 credential model

MT5 account access is based on account/login, password and trade-server identity. Production configuration should therefore use explicit broker/server/account allowlists rather than pretending that every broker behaves like a crypto exchange.

### Testnet becomes Demo + Paper for this project

For Ariatrading, the safe progression is:

```text
Research
  -> Backtest
  -> Out-of-sample
  -> Paper
  -> MT5 Demo
  -> Forward validation
  -> Separate LIVE release gate
```

The repository must not silently convert a successful demo/paper run into real-money execution.

### Ubuntu/VPS must follow the execution adapter

A generic bot checklist often assumes Ubuntu + systemd + Docker. MT5 Python integration is terminal-based and the official documentation demonstrates a Windows-oriented installation path. The deployment decision should therefore be made around the actual MT5 terminal and broker setup rather than forcing a Linux-first stack for appearance alone.

## Production dependency policy

Do not install every item in the checklist into the core runtime just because it appears on the list.

The dependency rules are:

1. Keep the core strategy deterministic and small.
2. Make exchange-specific tooling optional unless the project actually needs that venue.
3. Do not add TA-Lib merely to satisfy a checklist when price-action logic does not require it.
4. Do not make Redis the source of truth for orders, fills, or recovery.
5. Do not expose broker credentials to the browser or Worker frontend.
6. Do not allow the optional ML/research layer to bypass risk or execution gates.
7. Any future LIVE adapter must be separately tested, auditable, idempotent, and fail-closed.

## Current release boundary

**Current boundary: PAPER / DEMO only.**

MT5 market-data connectivity is already part of the repository, while the documented architecture keeps real execution behind a dedicated execution boundary. The 30-component checklist therefore represents the target production surface and highlights remaining implementation work instead of falsely claiming that all 30 are already operational.

## Minimum LIVE gate before real money

A future LIVE release should require all of the following to be true at the same time:

- verified broker/server/account identity
- explicit LIVE configuration and separate credentials
- broker contract validation including symbol, volume, price precision, stop/freeze constraints and filling mode
- preflight order validation before sending
- explicit broker retcode handling
- timeout/ambiguous execution handling without blind retry
- post-order position/deal reconciliation
- durable execution audit trail
- startup reconciliation after restart
- hard daily loss/drawdown kill switch
- stale-feed and abnormal-spread protection
- deterministic signal identity and idempotency
- complete unit/contract/integration/replay/failure-injection regression coverage
- real-time operational monitoring and Telegram alerts
- documented rollback/disable procedure

No profitability claim is implied by passing this engineering gate.
