# Bodyguard(Aria) — Data Protection Boundary

Bodyguard is not a trading strategy component. Its security scope is protecting Ariatrading/Webaria data and system boundaries from accidental disclosure and hostile requests.

## Protected boundary

```text
Browser / Internet
       |
       v
Cloudflare Worker + Bodyguard
       |
       +--> validate / rate-limit / probe block / CORS
       +--> redact logs and public JSON
       +--> block public execution surfaces
       |
       v
Trusted application runtime
       |
       +--> provider credentials stay in server/Worker secrets
       +--> MT5 runtime remains outside public HTTP authority
```

## Data-loss prevention rules

1. **Secrets stay server-side.** API keys, bearer tokens, passwords, private keys, cookies, and refresh/session tokens must never be committed to Git or placed in browser storage/bundles.
2. **Logs are sanitized before emission.** Sensitive key names and common secret-shaped values are replaced with `[REDACTED]`.
3. **Public JSON is sanitized.** The Worker applies the same redaction boundary to JSON responses so a future accidental secret field is not sent verbatim to the browser.
4. **Internal errors are not reflected.** Public error responses use generic messages instead of exposing stack traces, filesystem paths, provider errors, or configuration details.
5. **Payloads are bounded.** Recursive sanitization has maximum depth and collection-size limits to reduce abuse through oversized/nested objects.
6. **The browser is untrusted.** Client state is not an authorization mechanism and cannot grant broker access.

## Important limitation

No application-level module can guarantee that a public repository or a compromised host is safe. Real credentials must be stored in the deployment secret store and rotated if they are ever exposed. Git history should also be treated as public for this repository.

## Next hardening layers

- Repository/dependency secret scanning in CI.
- Strong CSP and browser isolation headers on the public site.
- Authentication/authorization for any future private API surface.
- Centralized, privacy-preserving security telemetry outside the public status endpoint.
- Credential rotation/runbook and incident-response tests.
