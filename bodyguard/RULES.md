# Bodyguard(Aria) Rules — v0.00.0

These rules are mandatory for anything under Bodyguard protection.

## R1 — Secrets never leave the server boundary
- API keys, tokens, broker credentials, private keys must live only in environment secrets / secure storage.
- Never put secrets in frontend JS, HTML, git commits, screenshots, or error messages.
- If a secret may have leaked: rotate immediately, then investigate.

## R2 — Least data in responses
- Public endpoints return only what the UI needs.
- No internal stack traces, file paths, account emails, phone numbers, or full request dumps to clients.
- Research journals and local browser storage are not treated as durable secure stores.

## R3 — Fail closed on uncertainty
- Invalid input, malformed JSON, unexpected methods, or failed integrity checks are rejected.
- Prefer `403` / `400` / `429` over partial processing of suspicious traffic.
- Do not “best-effort” continue when authentication or validation is ambiguous.

## R4 — Input is hostile until proven otherwise
- Validate symbol, timeframe, numeric ranges, and string length before use.
- Reject path traversal patterns, control characters, and oversized bodies.
- Never pass raw query strings into shell, eval, or dynamic code execution.

## R5 — Rate and abuse controls
- Public market endpoints must be rate-limited per IP / client fingerprint where possible.
- Repeated identical probing, burst traffic, or auth failures trigger cooldown / block signals.
- Caching is allowed for availability; it must not bypass auth or expose privileged data.

## R6 — No privilege through the browser
- Browser UI is untrusted. Paper trading state in localStorage is local simulation only.
- No endpoint may place real broker orders unless a future execution adapter is explicitly enabled behind separate gates.
- Admin or operator actions require separate strong authentication (not shipped in 0.00.0).

## R7 — Logging without leaking
- Security events are recorded with time, route, reason, and coarse client identity.
- Logs must scrub Authorization headers, cookies, API keys, and personal identifiers.
- Retain security logs long enough to investigate; do not ship them to public clients.

## R8 — Dependency and deploy hygiene
- Do not commit `.env`, key files, or Cloudflare token material.
- Deploy tokens stay in CI secrets.
- Review Worker / Pages permissions when connectors or secrets change.

## R9 — Personal data minimization
- Do not collect names, phone numbers, national IDs, or private messages in this stack unless a future feature explicitly requires it and documents consent + retention.
- Trading research data is market data + strategy state, not identity data.

## R10 — Change control
- Security rule changes bump Bodyguard version and update `RULES.md`.
- Disabling a guard requires an explicit config flag and a recorded reason.
- “Temporary” bypasses without expiry are forbidden.
