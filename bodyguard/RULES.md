# Bodyguard(Aria) Rules — v0.03.0

R1–R13 remain in force from 0.02.0.

## R14 — Observability without exposure (new)
Status and audit surfaces may expose only aggregate counters and version metadata.
They must never include secrets, raw IPs, tokens, emails, or request bodies.
