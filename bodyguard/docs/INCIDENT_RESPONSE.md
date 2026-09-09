# Bodyguard(Aria) Incident Response — v0.02.0

## API key leak
1. Rotate provider key immediately.
2. Update Cloudflare Worker secret.
3. Review git/CI logs.

## Probe / soft-ban noise
1. Check Worker logs for `probe_pattern_blocked` or `soft_ban_applied`.
2. Soft-ban is per isolate and expires automatically (~10 minutes default).
3. Do not whitelist attack patterns; fix client bugs instead.

## Abuse floods
1. Confirm UI polling is healthy.
2. Optionally lower `rateMax` in a follow-up config release.
3. Keep all execution paths closed.

## Personal data in logs
1. Stop the path.
2. Scrub logs.
3. Rotate related secrets if needed.

Standing rule: contain, rotate, patch, document — never retaliate.
