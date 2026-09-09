# Bodyguard(Aria) Threat Model — v0.01.0

## Assets
1. Worker source and Cloudflare config
2. Market-data API keys and future broker credentials
3. Strategy research code
4. Operator GitHub / Cloudflare access
5. Browser-local paper state

## Adversaries
1. URL scanners and bots
2. Quota burners / scrapers on `/api/signal` and `/api/price`
3. Secret hunters reading JS and error payloads
4. Malformed-input probers
5. Shared-device risk for localStorage paper state

## Controls active in 0.01.0
| Threat | Control |
|--------|---------|
| API flooding | per-IP path rate limit |
| Bad methods | allowlist GET/HEAD/OPTIONS on guarded routes |
| Bad symbol/tf | schema validation |
| Query abuse | max query length |
| Secret echo | safe public errors + rules |
| Order abuse | no execution surface on public Worker |
