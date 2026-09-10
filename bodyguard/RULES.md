# Bodyguard(Aria) Rules — v0.05.1

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

### R15 — Payload & Request Body Integrity
Incoming JSON payloads are checked against bounded byte size, nesting depth, and dangerous object properties such as `__proto__`, `constructor`, `prototype`, and `$where`.

### R16 — Execution Boundary & Command Isolation
The public Worker and Web layer have zero broker execution authority. Public requests targeting execution surfaces must be rejected. Broker interaction remains isolated inside the protected runtime boundary.

### R17 — CORS & Origin Protection
CORS enforces explicit origin allowlists. Wildcard `Access-Control-Allow-Origin: *` is prohibited on authenticated or stateful surfaces, and pre-flight requests are validated defensively.

### R18 — Real-Time Security Incident Reporting
Security events detected at runtime must be emitted immediately through the active telemetry path and be available to the monitoring/status surface as soon as the event is observed.

R18 requirements:
1. Detect → enforce → emit security event in the same request path whenever practical.
2. Record category, severity, timestamp, rule, endpoint class, action, count, and evidence reference.
3. Prefer near-real-time delivery; do not claim zero latency or guaranteed 100% delivery across provider/network failures.
4. Never silently discard a security event without an observable failure signal.
5. Runtime events must be sanitized before logging/persistence.
6. Durable reports in `bodyguard/Report/` are incident memory/evidence indexes, not a substitute for live telemetry.
7. Never attribute an attack to a specific person or organization without independent evidence.
8. Never fabricate attack events, counters, or incidents for dashboard/demo purposes.

## Incident workflow

```text
DETECT
  -> CLASSIFY
  -> BLOCK / RATE-LIMIT / SOFT-BAN / ALLOW
  -> EMIT TELEMETRY
  -> ALERT / STATUS SURFACE
  -> DURABLE INCIDENT REPORT
  -> INVESTIGATE
  -> RESOLVE + REGRESSION TEST
```

## Reporting boundary

The Bodyguard security status UI may expose aggregate and operationally useful information such as:
- current posture (`HEALTHY`, `ELEVATED`, `UNDER_ATTACK`)
- event categories and counts
- severity
- latest detection timestamp
- blocked/rate-limited/soft-banned totals
- incident/evidence references that contain no secrets or PII

It must not expose raw request bodies, credentials, permanent IP addresses, access tokens, filesystem paths, or internal stack traces.
