# Bodyguard(Aria) v0.02.0

Defensive security layer for Ariatrading / Webaria.

## Mission
Protect the system, secrets, and personal data from probing, abuse, injection attempts, and leakage.

## 0.02.0 highlights
- Suspicious **probe pattern** detection in path/query (traversal, XSS/SQL shaped tokens)
- **User-Agent risk signals** for empty/scanner-like clients
- **Soft-ban** window after repeated blocks from the same client key
- Stricter path allow behaviour for `/api/*`
- Security headers retained from 0.01.0

## Version ladder
| Version | Focus |
|---------|--------|
| 0.00.0 | foundation / rules |
| 0.01.0 | enforce validate + rate limit |
| **0.02.0** | **probe detection + soft-ban** |
| 0.03.x | optional audit sink / dashboard |

## Operator notes
- Soft-ban is in-memory per Worker isolate (resets on cold start)
- Legitimate browsers with normal UAs are unaffected
- UI polling rates remain under the API rate limit
