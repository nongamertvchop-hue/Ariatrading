# Bodyguard(Aria) Rules — v0.02.0

## R1 — Secrets never leave the server boundary
## R2 — Least data in responses
## R3 — Fail closed on uncertainty
## R4 — Input is hostile until proven otherwise
## R5 — Rate and abuse controls
## R6 — No privilege through the browser
## R7 — Logging without leaking
## R8 — Dependency and deploy hygiene
## R9 — Personal data minimization
## R10 — Change control
## R11 — Enforcement on the edge
## R12 — Probe patterns are blocked (new)
Path/query containing traversal, script/sql shaped probes, or encoded attack markers are rejected.
## R13 — Repeat offenders get a cool-down (new)
Clients that accumulate block events in a short window receive a temporary soft-ban.
