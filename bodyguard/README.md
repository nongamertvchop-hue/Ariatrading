# Bodyguard(Aria) v0.01.0

Defensive security layer for Ariatrading / Webaria.

**Mission:** protect the system, secrets, and personal data from probing, abuse, and leakage.

## What changed in 0.01.0
- Enforcement is **active** on the Worker gateway (`worker/entry.js`)
- Public `/api/*` requests pass method, query, symbol/timeframe, and rate-limit checks
- Security events are logged in structured JSON (no secrets)
- Response header `x-bodyguard: 0.01.0` marks guarded responses

## Layout
```text
bodyguard/
  VERSION
  README.md
  RULES.md
  THREAT_MODEL.md
  config/bodyguard.config.json
  core/policy.py
  core/sanitize.py
  worker/bodyguard.js
  docs/INCIDENT_RESPONSE.md
```

## Modes
| Version | Mode | Behavior |
|---------|------|----------|
| 0.00.0 | monitor | helpers only |
| **0.01.0** | **enforce** | blocks bad requests on Worker |
| 0.02.x | harden | tighter limits, bot scores, audit sink |

## Operator notes
- Rate limit defaults: 60 requests / IP / path / 60 seconds on `/api/*`
- Legitimate UI polling (signal ~45s, price ~8s) stays well under the limit
- If you are blocked with HTTP 429, wait for the window to reset
- Still no real order execution path
