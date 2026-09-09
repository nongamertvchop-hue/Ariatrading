# Bodyguard(Aria) v0.04.0

Defensive security layer for Ariatrading / Webaria.

## 0.04.0 highlights
- Webaria page: `/bodyguard.html` — live status dashboard
- Alert thresholds on status payload (`alerts[]`)
- Still defensive only; no secrets or IPs exposed

## Endpoints
- `GET /api/bodyguard/status`
- UI: `https://<worker>/bodyguard.html`

## Version ladder
| Version | Focus |
|---------|--------|
| 0.01.0 | enforce + rate limit |
| 0.02.0 | probe + soft-ban |
| 0.03.0 | status + counters |
| **0.04.0** | **status UI + thresholds** |
