# Bodyguard(Aria) Threat Model — v0.05.0

## Assets
1. Worker source and Cloudflare config
2. Market-data API keys and future broker credentials (MT5, Telegram tokens)
3. Strategy research and quantitative model code
4. Operator GitHub / Cloudflare access
5. Browser-local paper state

## Adversaries
1. URL scanners and automated penetration bots
2. Quota burners / scrapers on `/api/signal` and `/api/price`
3. Secret hunters reading JS bundles and error payloads
4. Malformed-input and prototype pollution probers
5. Cross-origin request forgery / malicious embedding sites
6. Order execution interceptors attempting unauthorized broker trades
7. Shared-device risk for localStorage paper state

## Controls active in 0.05.0
| Threat | Control | Rule |
|--------|---------|------|
| API flooding | per-IP sliding window rate limit | R5 |
| Bad HTTP methods | allowlist GET/HEAD/OPTIONS on guarded routes | R3 |
| Bad symbol/tf | strict schema validation & regex | R4 |
| Query abuse | max query length (512 chars) | R4 |
| Secret echo | automated redactor for keys, JWTs, Telegram tokens, passwords | R1, R7 |
| Probe & traversal | regex pattern blocking + double-encoding evasion check | R12 |
| Repeat attacks | automatic cooldown soft-ban | R13 |
| Status leakage | aggregate counters only, zero PII or IP exposure | R14 |
| Prototype pollution | deep object inspection blocking `__proto__`, `constructor`, `prototype` | R15 |
| Order/Execution abuse | strict execution barrier; public edge rejects trading paths | R16 |
| CORS spoofing | origin allowlist enforcement & pre-flight inspection | R17 |
