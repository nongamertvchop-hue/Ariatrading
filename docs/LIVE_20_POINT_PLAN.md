# Ariatrading — LIVE Trading Readiness: 20-point engineering plan

Goal: make the system capable of operating against a real MT5 account without removing the controls required to keep broker failures, stale data, duplicate orders, and configuration mistakes from becoming uncontrolled execution.

## 20 workstreams

1. **LIVE execution tier** — `ALERT_ONLY/DEMO/LIVE` in one explicit execution policy.
2. **MT5 account reconciliation** — requested mode must match the connected account type.
3. **Runtime preflight** — permissions, account state, journal recovery, and configuration checks before starting.
4. **Continuous live loop** — completed candles/ticks continuously feed the existing orchestrator.
5. **Completed-candle discipline** — forming candles never enter signal evaluation.
6. **Tick freshness gate** — stale broker ticks stop new entries.
7. **Spread gate** — abnormal spread stops new entries.
8. **Broker contract validation** — symbol digits, point, tick value/size, and volume constraints come from MT5.
9. **Risk sizing** — strategy candidates pass the existing Forex risk engine before execution.
10. **Daily circuit breaker** — persisted session equity baseline blocks new entries after the configured drawdown limit.
11. **Idempotency journal** — deterministic intent IDs prevent duplicate submissions across restarts.
12. **Ambiguous-outcome recovery** — transport uncertainty becomes a manual reconciliation state, never a blind retry.
13. **Broker-side `order_check`** — every opening/closing request is checked before `order_send`.
14. **SL/TP validation** — mandatory protective stop and direction-consistent target validation.
15. **Position ownership** — strategy magic number isolates positions managed by Ariatrading.
16. **Position reconciliation** — each cycle observes broker positions before evaluating new entries.
17. **Kill/fail-closed behavior** — missing feed, account mismatch, journal corruption, or broker uncertainty blocks execution.
18. **Operational telemetry** — structured logs and notifications expose signal, risk, broker, and execution outcomes.
19. **Restart safety** — persistent state and unreconciled-intent detection prevent unsafe recovery after process failure.
20. **Automated verification** — unit tests, contract tests, and CI checks cover the live boundary; no claim of production readiness is made until CI is green.

## Current implementation status

- 1–3: implemented, plus explicit Stage 1 account/server allowlisting.
- 4: implemented in `live/live_runtime.py` and wired through the canonical CLI.
- 5–9: implemented across MT5 feed, executor, strategy, and runtime gates.
- 10: implemented as `DailyCircuitBreaker`, with Stage 1 capped at 1% daily drawdown.
- 11–12: implemented by `ExecutionJournal` and ambiguous-state handling.
- 13–15: implemented in `MT5LiveExecutor`.
- 16–19: implemented by the live runtime boundary, journal recovery checks and Stage 1 policy.
- 20: automated tests cover Stage 1 policy, account identity and CLI defaults; branch CI must still be observed before promotion.

## Stage 1 production boundary

The first real-money tier is deliberately narrow:

- exactly one allow-listed symbol
- exact MT5 login + server identity
- explicit operator opt-in
- maximum 0.25% risk per trade
- maximum 1% daily equity drawdown
- maximum 20-point spread
- maximum 5-second tick age

These are deployment controls, not new strategy rules.

## Non-negotiable architecture rules

- Strategy code does not know broker credentials.
- MQL5/MT5 is an execution/data adapter, not a second strategy brain.
- LIVE does not bypass risk or validation gates.
- A broker timeout is not equivalent to a rejected order.
- An unknown position state blocks automatic duplicate submission.
- No look-ahead data: only completed candles are eligible for strategy evaluation.
- No production-readiness claim is valid until tests and CI verify the implementation.
