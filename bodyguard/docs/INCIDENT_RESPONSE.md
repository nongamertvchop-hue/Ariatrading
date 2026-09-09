# Bodyguard(Aria) Incident Response — v0.03.0

## Quick status check
```http
GET /api/bodyguard/status
```
Inspect `counters.blocked`, `rate_limited`, `probes`, `soft_bans`.
No IPs or secrets are returned.

## API key leak
1. Rotate provider key.
2. Update Cloudflare secret.
3. Review git/CI logs.

## Probe noise / soft-ban
1. Read Worker logs for `probe_pattern_blocked` / `soft_ban_applied`.
2. Soft-ban expires automatically.
3. Do not whitelist attack patterns.

## Abuse floods
1. Confirm UI polling health.
2. Optionally lower rate limits in a later release.
3. Keep execution paths closed.

Standing rule: contain, rotate, patch, document — never retaliate.
