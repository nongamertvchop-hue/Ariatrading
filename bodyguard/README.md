# Bodyguard(Aria) v0.00.0

Defensive security layer for the Ariatrading / Webaria stack.

**Purpose:** protect the system, operators, and personal data from unauthorized access, probing, credential theft, and abuse of public endpoints.

This package is **defensive only**. It does not attack other systems.

## What it protects

1. Public Worker / Webaria endpoints from abuse and scraping
2. Secrets and API keys from accidental exposure
3. Personal / account data from leakage through logs and responses
4. Application integrity from obvious injection and malformed input
5. Operational visibility via security event records

## Layout

```text
bodyguard/
  VERSION                 # package version
  README.md               # this file
  RULES.md                # hard security rules (policy)
  THREAT_MODEL.md         # what we assume and defend against
  config/
    bodyguard.config.json # tunable guard settings
  core/
    policy.py             # rule evaluation helpers (Python research side)
    sanitize.py           # input/output sanitization helpers
  worker/
    bodyguard.js          # Worker-side request guard primitives
  docs/
    INCIDENT_RESPONSE.md  # what to do when something looks wrong
```

## Version policy

- `0.00.x` = foundation / policy / scaffolding only
- `0.01.x` = enforced request guards on Worker
- `0.1.x`  = integrated with production deploy path
- `1.0.0`  = locked baseline after review

## Integration note

v0.00.0 ships rules, config, and helper modules. Enforcement wiring into `worker/entry.js` is intentional next work so this release stays reviewable and low-risk.
