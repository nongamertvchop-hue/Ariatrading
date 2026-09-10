# Ariatrading Version

Current version: **0.16.1**

## Versioning rule

Every meaningful strategy or architecture change must update this file and the version block in `README.md`.

Use semantic versioning:
- **MAJOR**: incompatible strategy/architecture change.
- **MINOR**: new strategy capability that remains backward compatible.
- **PATCH**: bug fix, test improvement, documentation, or non-strategy correction.

## Current milestone — 0.16.1 — realtime web/runtime boundary hardening

- Core strategy remains exactly two setups: LONG at support and SHORT at resistance.
- Backtest/realtime/paper safety boundaries remain unchanged and real broker execution remains disabled.
- Webaria `/api/market` now treats the MT5 runtime as the canonical market source and fails closed when the runtime bridge is not configured.
- The runtime API exposes an authenticated `/market` endpoint for completed MT5 candles and current market telemetry.
- Runtime API authentication can be enabled with `RUNTIME_API_TOKEN`; Cloudflare Pages uses the same secret through `MT5_RUNTIME_API_URL` + `RUNTIME_API_TOKEN`.
- Webaria Bodyguard now reads sanitized durable runtime events and heartbeat telemetry instead of relying on ephemeral Worker-isolate memory.
- Bodyguard telemetry intentionally exposes actor class, category, severity and reason only; IPs, secrets, request bodies and PII remain excluded.
- CI syntax coverage includes the new Bodyguard status endpoint and canonical market endpoint.
- MT5 remains read-only and no real broker execution path is implemented.

## Release interpretation

A 0.16.1 PASS means the tested engineering properties held for the selected code revision and historical fixture. It does not establish profitability, future performance, or permission to use real money.

## Next milestone

### 1.0.0 — only after extended paper evidence
- Extend historical coverage and long-duration paper observation.
- Freeze a documented strategy specification only after out-of-sample and robustness checks.
- Keep any future broker execution component isolated from the research engine and fail closed on uncertainty.
