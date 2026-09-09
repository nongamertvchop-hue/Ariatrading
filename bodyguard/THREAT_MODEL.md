# Bodyguard(Aria) Threat Model — v0.00.0

## Assets
1. Cloudflare Worker source and configuration
2. Twelve Data API key and any future broker credentials
3. Strategy research code and paper journals
4. Operator GitHub / Cloudflare account access
5. End-user browser session data (local paper state)

## Adversaries (assumed)
1. Opportunistic scanners hitting public URLs
2. Scrapers / quota burners against market endpoints
3. Attackers probing for exposed secrets in JS and error text
4. Attackers sending malformed input to trigger faults
5. Insiders or shared-device risk for local browser state

## Out of scope for v0.00.0
- Full WAF product replacement
- Physical device security
- Legal takedown processes
- Offensive counter-hacking

## Primary controls in this version
| Threat | Control |
|--------|---------|
| Secret exposure in client | R1, response scrubbing helpers |
| Abuse of `/api/*` | rate-limit config, method allowlists |
| Injection via query params | sanitize + schema validation |
| Information leak in errors | safe error envelopes |
| Accidental git secret commit | rules + checklist |
| Chart/API abuse loops | client + server cooldown settings |

## Trust boundaries
1. **Browser** — untrusted
2. **Worker public routes** — semi-trusted, must validate everything
3. **Cloudflare secrets / env** — trusted store
4. **GitHub private workflow secrets** — trusted store
5. **Local developer machine** — operator-controlled, still keep secrets out of repo
