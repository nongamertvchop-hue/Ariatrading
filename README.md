# Ariatrading

Educational price-action research and paper-automation project for EURUSD-style OHLC data.

**Current version: 0.15.1**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No unrelated entry patterns are added. Context layers can filter, score, or validate these two setups, but cannot create a third setup.

## Architecture

The project is layered so every stage can be used together without duplicating strategy rules:

1. **Market structure** — confirmed swing highs/lows are labeled HH, HL, LH and LL, producing a structural bias.
2. **Zone intelligence** — repeated confirmed swings form support/resistance zones with independent, time-separated reactions and recent-break invalidation.
3. **Candle intelligence** — completed candles provide descriptive buying/selling pressure and reject non-finite OHLC values.
4. **Sequence engine** — APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM.
5. **Fake-breakout engine** — fake breaks enter the explicit reclaim path; true breaks block the setup.
6. **Multi-timeframe context** — higher/entry structure can filter and score an existing setup. Timestamp alignment prevents higher-timeframe look-ahead.
7. **Setup scoring** — transparent 0-100 heuristic quality score; never treated as win probability.
8. **Risk/backtest** — hypothetical SL/TP planning and sequential historical simulation.
9. **Execution simulation** — optional spread, commission, slippage, latency, session and precision effects, isolated from strategy decisions.
10. **Research validation** — chronological splits, R-based metrics, profit factor, drawdown and bootstrap expectancy uncertainty.

## Automation boundary

The current automation path is deliberately paper-only:

```text
Closed market candle
      |
      v
RealtimeMonitor
      |
      v
PaperSessionRunner
      |
      +--> signal journal (deterministic event identity)
      |
      +--> next-bar paper entry
      |
      +--> paper position lifecycle
      |
      +--> atomic runtime checkpoint
      |
      +--> cross-component reconciliation
      |
      v
PAPER runtime
```

A restart must not blindly trust one restored object. The reconciliation layer checks the relationships between the paper position, journal OPEN/CLOSE events, account counters, pending signal and last processed candle before allowing the session to continue.

The runtime uses atomic JSON checkpoint replacement for the current single-process research/paper phase. This is not yet a multi-process or distributed execution store; scaling that boundary will require transactional persistence and concurrency/fencing controls.

`ExecutionMode.DEMO` remains explicitly rejected. There is still no MT5 order-sending adapter, and MT5 integration remains read-only.

## Development safety rules

- Closed-candle decisions only.
- A signal from bar N can only fill on a later bar, never on bar N itself.
- Duplicate or old candles are ignored before mutating paper state.
- Unexpected runtime errors fail closed by default.
- Checkpoint persistence errors are not swallowed.
- Restore errors halt the runtime rather than attempting automatic ledger repair.
- Strategy logic and execution simulation remain separate.
- No live broker orders are sent by this repository.
