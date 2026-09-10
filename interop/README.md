# Polyglot Data Plane

Ariatrading uses one canonical OHLC data contract so multiple runtimes can participate in the same market-data pipeline without duplicating the trading strategy.

## Roles

- **Python** — research orchestration, features/ML, canonical validation, and integration.
- **Go** — streaming-style ingress normalization and cheap early validation.
- **Rust** — deterministic native validation for throughput-oriented research batches.
- **C++** — low-level numeric validation for large historical batches.
- **Java** — long-running service-style validation and dataset processing.
- **JavaScript/Cloudflare Worker** — browser/API delivery and realtime UI integration already present in `worker/` and `Webaria/`.

These components do **not** implement independent LONG/SHORT strategies. They validate, normalize, or transport the same market data before it reaches the Python strategy boundary.

## Wire protocol

Native validators use UTF-8 tab-separated values (TSV):

```text
1725900000\t1.1000\t1.1020\t1.0990\t1.1010
```

Field order is `time`, `open`, `high`, `low`, `close`, with optional `volume` as the sixth field. Validators emit one JSON object per input line. Successful records contain `ok:true`; malformed or out-of-order records contain `ok:false` and a stable `error` message.

The logical record shape is documented in `interop/market_data.schema.json`. The Python CLI is a JSONL convenience entrypoint for Python-native workflows; `strategy/polyglot_bridge.py` uses the common TSV wire protocol when invoking native validators.

No adapter silently repairs invalid prices. All implementations enforce finite positive prices, candle geometry, and strictly increasing timestamps.

## Safety boundary

The polyglot data plane is research/paper/demo infrastructure. It has no broker-order capability. It must not be used as evidence that a strategy is profitable, and it must not bypass the runtime research contract in `strategy/research_rules.py`.

See `docs/RESEARCH_AND_INNOVATION_RULES.md` for the research contract.
