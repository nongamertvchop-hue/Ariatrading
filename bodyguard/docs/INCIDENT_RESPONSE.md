# Bodyguard(Aria) Incident Response — v0.01.0

## API key leak
1. Rotate provider key immediately.
2. Update Cloudflare Worker secret.
3. Review git/CI for accidental prints.

## Abuse / 429 storms
1. Confirm legitimate UI polling is not the source.
2. Tighten `rateMax` in a follow-up release if needed.
3. Keep execution paths closed.

## Personal data in logs
1. Stop the path.
2. Scrub logs.
3. Treat as privacy incident.

## Account compromise (GitHub / Cloudflare)
1. Revoke sessions and tokens.
2. Rotate all secrets.
3. Redeploy only from known-good commit.

Standing rule: contain, rotate, patch, document — never retaliate.
