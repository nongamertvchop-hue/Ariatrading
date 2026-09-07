# Ariatrading

Educational price-action research and paper-automation project for EURUSD-style OHLC data.

**Current version: 0.16.0**

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

Historical validation now uses the same runtime path rather than a second strategy:

```text
Historical closed candles
        |
        v
strategy.paper_replay
        |
        +--> RealtimeMonitor
        |       |
        |       +--> closed-candle integrity / freshness checks
        |       +--> existing strategy engine
        |
        +--> PaperSessionRunner
                |
                +--> signal on bar N
                +--> paper entry only at a later bar OPEN
                +--> paper position lifecycle + journal
```

A restart must not blindly trust one restored object. The reconciliation layer checks the relationships between the paper position, journal OPEN/CLOSE events, account counters, pending signal and last processed candle before allowing the session to continue.

The runtime uses atomic JSON checkpoint replacement for the current single-process research/paper phase. This is not yet a multi-process or distributed execution store; scaling that boundary will require transactional persistence and concurrency/fencing controls.

`ExecutionMode.DEMO` remains explicitly rejected. There is still no MT5 order-sending adapter, and MT5 integration remains read-only.

## Historical paper replay contract

`strategy.paper_replay.replay_paper_session()` is intended for long-run paper validation and replay parity checks. For each replay step it exposes only a historical prefix ending at the current closed candle. The resulting evaluation timestamp is deterministic for reproducible research artifacts.

The replay deliberately preserves the live-session timing contract: a directional signal discovered on candle N is stored as pending state and can only be opened on a later candle, using that later candle's OPEN as the simulated fill reference. Future candles are never supplied to the monitor before their replay step.

This is a validation harness, not a profitability claim. It does not send MT5 orders and does not promote the system toward live execution by itself.

## Development safety rules

- Closed-candle decisions only.
- A signal from bar N can only fill on a later bar, never on bar N itself.
- Duplicate or old candles are ignored before mutating paper state.
- Unexpected runtime errors fail closed by default.
- Checkpoint persistence errors are not swallowed.
- Restore errors halt the runtime rather than attempting automatic ledger repair.
- Strategy logic and execution simulation remain separate.
- Historical replay must use the same realtime monitor and paper-session path; do not create a parallel strategy implementation.
- No live broker orders are sent by this repository.
