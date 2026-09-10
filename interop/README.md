# Polyglot Data Plane

Ariatrading uses a language-neutral JSON Lines contract so multiple runtimes can participate in the same market-data pipeline without duplicating the trading strategy.

## Roles

- **Python** — research orchestration, feature/ML work, and contract-level integration.
- **Go** — streaming ingress normalization and cheap early validation.
- **Rust** — deterministic high-throughput candle validation and aggregate statistics.
- **C++** — low-level numeric validation and range statistics for large historical batches.
- **Java** — long-running service-style validation and dataset summaries.
- **JavaScript/Cloudflare Worker** — browser/API delivery and realtime UI integration already present in `worker/` and `Webaria/`.

These components do **not** implement independent LONG/SHORT strategies. They validate, normalize, summarize, or transport the same canonical OHLC data before it reaches the Python strategy boundary.

## Protocol

Input is UTF-8 JSONL. Each non-empty line is one candle:

```json
{"time":1725900000,"open":1.1000,"high":1.1020,"low":1.0990,"close":1.1010}
```

Each implementation emits JSONL records:

```json
{"ok":true,"index":0,"time":1725900000,"open":1.1,"high":1.102,"low":1.099,"close":1.101}
```

Malformed records emit `ok:false` with a stable `error` field. No adapter silently repairs invalid prices.

## Safety boundary

The polyglot data plane is research/paper/demo infrastructure. It has no broker-order capability. It must not be used as evidence that a strategy is profitable, and it must not bypass the runtime research contract in `strategy/research_rules.py`.

See `interop/market_data.schema.json` for the canonical record shape and `docs/RESEARCH_AND_INNOVATION_RULES.md` for the research contract.