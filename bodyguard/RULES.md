# Bodyguard(Aria) Rules — v0.01.0

Mandatory defensive rules.

## R1 — Secrets never leave the server boundary
API keys, tokens, broker credentials stay in environment secrets only. Never in frontend, git, or error text.

## R2 — Least data in responses
Public endpoints return only UI-needed fields. No stack traces, paths, emails, or secret material.

## R3 — Fail closed on uncertainty
Invalid method, malformed input, or failed checks are rejected (400/403/405/429). No partial processing of suspicious traffic.

## R4 — Input is hostile until proven otherwise
Validate symbol, timeframe, query length. Reject control characters and oversized input.

## R5 — Rate and abuse controls
Public market endpoints are rate-limited per IP + path. Burst abuse is blocked.

## R6 — No privilege through the browser
Browser is untrusted. No real broker order placement from public UI paths.

## R7 — Logging without leaking
Security events log time, route, reason, coarse client key. Scrub Authorization, cookies, API keys.

## R8 — Dependency and deploy hygiene
No `.env` or token files in git. CI secrets only.

## R9 — Personal data minimization
Do not collect identity data unless a documented feature requires it.

## R10 — Change control
Security changes bump Bodyguard version. Temporary bypasses without expiry are forbidden.

## R11 — Enforcement on the edge (new in 0.01.0)
Worker entry must run Bodyguard checks before market handlers for `/api/*`.
