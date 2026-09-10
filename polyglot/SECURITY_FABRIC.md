# Polyglot Security Fabric

## Current verified implementation inventory

This repository currently contains real source implementations in Python, JavaScript, C++, Go, Java, and Rust. `polyglot/languages.json` is a capability registry, not proof that every listed language is installed or operational.

`polyglot/security_inventory.py` scans the repository itself and reports source presence plus locally discoverable toolchains. This prevents the security system from claiming support that does not exist.

## Security roles

| Language | Real role | Security value |
|---|---|---|
| Python | policy, inventory, evidence, orchestration | central fail-closed control plane |
| JavaScript | Bodyguard/Worker boundary | HTTP, CORS, route and payload enforcement |
| C++ | independent OHLC validator | strict numeric and geometry cross-check |
| Go | independent streaming validator | independent parser and stream semantics |
| Java | independent strict parser | independent runtime/type-system cross-check |
| Rust | independent validator | memory-safe independent cross-check |

The native validators are intentionally not allowed to place orders or receive broker credentials.

## Real verification path

1. CI builds the C++, Go, Java, and Rust validators from repository source.
2. Python creates a deterministic validation corpus containing valid candles and adversarial malformed candles.
3. Each native implementation receives the same corpus independently.
4. Every implementation must accept known-valid records and reject malformed geometry, duplicate/out-of-order timestamps, non-finite prices, and negative volume.
5. A missing executable, timeout, non-zero exit, malformed JSON, wrong record count, false acceptance, or false rejection fails the gate.
6. The gate requires all four independent native validators to agree. There is no majority vote that can hide a broken validator.

## Defense-in-depth boundary

This fabric is an additional evidence layer. It does not replace Bodyguard, the system gate, broker contract validation, reconciliation, execution recovery, or paper/demo isolation.

A language worker is never a source of authority for LIVE execution. Cross-language agreement can increase confidence in data integrity; it cannot authorize an order.

## Scale and failure notes

The current quorum is deliberately synchronous and CI-oriented. It is suitable for deterministic security regression testing, not for putting four compiler runtimes on every realtime market tick. Realtime production use should call a pre-built, isolated verification service only after measured latency and resource limits are established.

Worker processes receive a minimal environment and no application credentials. This is intentional containment, not a substitute for OS/container sandboxing.

## Next expansion rule

Additional languages may become operational only by adding a concrete worker, an explicit role, independent regression coverage, and CI toolchain verification. Adding a language name alone never increases the security level.
