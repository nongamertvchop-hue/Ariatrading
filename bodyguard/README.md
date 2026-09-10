# Bodyguard(Aria) v0.05.0 — aegis-shield

Defensive security layer for Ariatrading, Webaria, and Cloudflare Worker layers.

## 0.05.0 highlights
- **Rule R15**: Payload & Request Body Integrity (prototype pollution protection: `__proto__`, `constructor`, `prototype`, depth <= 5).
- **Rule R16**: Execution Boundary Isolation (blocks `/api/order`, `/api/execute`, `order_send` from public edge).
- **Rule R17**: CORS & Origin Defense (strict origin allowlists, pre-flight `OPTIONS` validation).
- Double-URL encoding (`%252e%252e`) & null-byte probe detection.
- Secret scrubbing enhanced for Telegram Bot Tokens, MT5 passwords, and JWTs.
- Webaria page: `/bodyguard.html` updated with posture badge and execution/CORS telemetry counters.

## Endpoints
- `GET /api/bodyguard/status`
- UI: `https://<worker>/bodyguard.html`

## Version ladder
| Version | Focus | Status |
|---------|-------|--------|
| 0.01.0 | enforce + rate limit | Complete |
| 0.02.0 | probe + soft-ban | Complete |
| 0.03.0 | status + counters | Complete |
| 0.04.0 | status UI + thresholds | Complete |
| **0.05.0** | **payload integrity + execution isolation + CORS** | **Enforced & Active** |
