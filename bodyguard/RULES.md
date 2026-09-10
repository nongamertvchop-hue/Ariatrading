# Bodyguard(Aria) Rules — v0.05.0

Comprehensive defensive security rules for Ariatrading, Webaria, and Cloudflare Worker layers.

---

## Core Security Rules

### R1 — Secrets never leave the server boundary
Private keys, provider tokens (e.g. Twelve Data, MT5, Telegram bot tokens, Cloudflare credentials) must never be embedded in public JavaScript, responses, or client-side storage.

### R2 — Least data in responses
API responses expose only fields strictly necessary for the caller. Redundant debugging context, internal stack traces, and environment metadata are stripped.

### R3 — Fail closed on uncertainty
Any unhandled exception, unrecognized HTTP method, ambiguous path, or malformed schema defaults immediately to a safe rejection (400, 403, 404, or 405).

### R4 — Input is hostile until proven otherwise
All parameters (symbols, timeframes, query strings, headers) are validated against strict allowlists and regex patterns before processing.

### R5 — Rate and abuse controls
Per-IP sliding-window rate limiting throttles abusive traffic and quota-burning requests on public market-data endpoints.

### R6 — No privilege through the browser
The browser runtime is strictly untrusted. Client-side local state (e.g. paper trading positions) cannot alter server calculations or issue broker commands.

### R7 — Logging without leaking
Log payloads must sanitize and scrub API keys, passwords, bearer tokens, emails, and sensitive identifiers before persistence or console output.

### R8 — Dependency and deploy hygiene
Minimize external dependencies. Zero-dependency standard library implementations are preferred for defensive runtime boundaries.

### R9 — Personal data minimization
No personally identifiable information (PII) such as user emails, phone numbers, or residential IP addresses are tracked or permanently logged.

### R10 — Change control & test provenance
Every defensive rule change must be accompanied by automated unit tests and deterministic version increments.

### R11 — Enforcement on the edge
Defensive filters run on Cloudflare Workers before requests reach upstream data sources or compute layers.

### R12 — Probe patterns are blocked
Requests containing directory traversal (`..`, `%2e%2e`), SQL injection tokens (`union select`, `drop table`), cross-site scripting (`<script>`, `javascript:`), or control characters are rejected with 403 Forbidden.

### R13 — Repeat offenders get a cool-down (Soft-Ban)
Clients that accumulate repeated policy violations within a short window are placed on an automatic temporary cooldown (soft-ban) without human intervention.

### R14 — Observability without exposure
Status and audit surfaces (`/api/bodyguard/status`, `/bodyguard.html`) may expose only aggregate counters and version metadata. They must never disclose IPs, tokens, or request bodies.

---

## New in v0.05.0

### R15 — Payload & Request Body Integrity (new)
Any incoming JSON payload is checked against:
1. Maximum byte limit (8KB default).
2. Maximum nesting depth (5 levels).
3. **Prototype Pollution Protection**: Automatic rejection of dangerous object properties (`__proto__`, `constructor`, `prototype`, `$where`).

### R16 — Execution Boundary & Command Isolation (new)
The public Worker and Web layer have zero execution authority:
- Any incoming request targeting trading endpoints (`/api/order`, `/api/execute`, `order_send`, `buy`, `sell`) is strictly blocked.
- Broker interaction is isolated inside the protected local/server `live/` runtime boundary and cannot be triggered via public HTTP endpoints.

### R17 — CORS & Origin Protection (new)
Cross-Origin Resource Sharing (CORS) enforces strict origin allowlists:
- Wildcard `Access-Control-Allow-Origin: *` is prohibited on authenticated or stateful surfaces.
- Pre-flight `OPTIONS` requests are handled defensively with explicit allowed headers and methods.
