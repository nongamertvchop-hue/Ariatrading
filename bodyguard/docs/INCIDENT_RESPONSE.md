# Bodyguard(Aria) Incident Response — v0.00.0

## If an API key may have leaked
1. Rotate the key at the provider (Twelve Data / Cloudflare / broker) immediately.
2. Update Cloudflare Worker secrets.
3. Review Git history and CI logs for accidental prints.
4. Record time, scope, and who rotated the key.

## If the public site is under abusive traffic
1. Enable stricter rate limits in `bodyguard.config.json` (next enforcement release).
2. Temporarily reduce polling frequency in Webaria UI.
3. Check Cloudflare analytics for IP bursts.
4. Keep market endpoints read-only — never open execution paths under pressure.

## If personal data appears in logs or responses
1. Stop the leaking path (config / code rollback).
2. Scrub stored logs where possible.
3. Treat as a privacy incident even if volume is small.

## If GitHub or Cloudflare account looks compromised
1. Revoke sessions and tokens.
2. Rotate all secrets.
3. Review recent deploys and repository commits.
4. Re-deploy only from a known-good commit.

## Standing rule
Bodyguard does not perform retaliation or counter-attacks. Contain, rotate, patch, document.
