# Bodyguard(Aria) — Defense-in-Depth Map

The goal is not literally one million copies of the same filter. The goal is to make compromise require crossing many independent boundaries, with fail-closed behavior at each boundary.

## Layer families

1. **Repository** — secret scanning and tracked-file hygiene.
2. **Dependency** — dependency review and minimal third-party surface.
3. **Build** — syntax/tests/security gates must pass before deployment.
4. **Deployment** — secrets remain in the platform secret store, never source or client bundles.
5. **Edge** — Cloudflare request filtering, method/path allowlists, rate limiting, probe detection and soft bans.
6. **Input** — strict schema, bounded payloads, nesting limits and prototype-pollution rejection.
7. **Browser** — CSP, frame isolation, permissions restrictions and same-origin resource policy.
8. **Application** — least-data responses, generic public errors and output redaction.
9. **Logging** — attacker-controlled values are sanitized before emission.
10. **Authorization** — future private/admin surfaces must authenticate and authorize server-side.
11. **Execution isolation** — public HTTP has no broker execution authority.
12. **Monitoring** — aggregate security counters and attack posture without exposing PII or secrets.
13. **Recovery** — credential rotation and incident-response procedures are mandatory after suspected exposure.

## Non-negotiable invariant

A security layer must never become a data-exfiltration channel itself. Security telemetry is therefore aggregate-first, and public status must not reveal IP addresses, credentials, request bodies, filesystem paths, stack traces, or environment secrets.

## Scaling rule

Do not add hundreds of redundant regexes just to increase the layer count. Prefer orthogonal controls: different failure modes, different trust boundaries, different authorities, and independent tests. This produces real defense-in-depth instead of security theater.
