# Bodyguard(Aria) v0.05.1 — aegis-shield

Defensive security layer for Ariatrading, Webaria, and Cloudflare Worker layers.

## 0.05.1 highlights
- **R15**: Payload & Request Body Integrity (prototype pollution protection, bounded nesting/body size).
- **R16**: Execution Boundary Isolation (public edge has no broker execution authority).
- **R17**: CORS & Origin Defense (strict origin allowlist and pre-flight validation).
- **R18**: Real-Time Security Incident Reporting.
- Runtime security events receive a timestamp, category, severity, reason and sanitized operational context.
- Latest security events are exposed through `/api/bodyguard/status` and rendered by `Webaria/bodyguard.html`.
- Live UI refreshes the security status every 2 seconds with `cache-control: no-store`.
- Durable incident memory and evidence index lives under `bodyguard/Report/`.

## Real-time guarantee boundary

Bodyguard is designed for **near-real-time detection and reporting**, not a false promise of zero latency or mathematically guaranteed 100% delivery. The current recent-event buffer is bounded and ephemeral to the Worker isolate.

For globally durable, cross-isolate event history, a persistent telemetry backend (for example Cloudflare-native durable analytics/storage) must be connected separately. Until then, runtime console telemetry plus the status surface are the live source of truth, while `bodyguard/Report/` stores verified incidents/evidence references.

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
| 0.05.0 | payload integrity + execution isolation + CORS | Complete |
| **0.05.1** | **real-time security event telemetry + incident reporting** | **Enforced & Active** |
