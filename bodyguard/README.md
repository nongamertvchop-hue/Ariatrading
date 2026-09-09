# Bodyguard(Aria) v0.03.0

Defensive security layer for Ariatrading / Webaria.

## Mission
Protect the system, secrets, and personal data from probing, abuse, injection attempts, and leakage — with basic observability.

## 0.03.0 highlights
- Public **status endpoint**: `GET /api/bodyguard/status`
- In-memory **audit counters** (allowed / blocked / rate-limited / probes / soft-bans)
- Status payload contains **no secrets, no IPs, no personal data**
- Webaria UI security notes (`bodyguard/web/SECURITY_UI.md`)
- Retains 0.02.0 probe detection + soft-ban + rate limits

## Version ladder
| Version | Focus |
|---------|--------|
| 0.00.0 | foundation |
| 0.01.0 | enforce validate + rate limit |
| 0.02.0 | probe detection + soft-ban |
| **0.03.0** | **status + audit counters** |

## Status endpoint example
```http
GET /api/bodyguard/status
```
Returns version, mode, and coarse counters only.
