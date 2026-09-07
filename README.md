# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.9.1**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No unrelated entry patterns are added. Context layers can filter, score, or validate these two setups, but cannot create a third setup.

## Architecture

The project is layered so every stage can be used together without duplicating strategy rules:

1. **Market structure** — confirmed swing highs/lows are labeled HH, HL, LH and LL, producing a structural bias.
2. **Zone intelligence** — repeated confirmed swings form support/resistance zones.
3. **Candle intelligence** — completed candles provide descriptive buying/selling pressure.
4. **Sequence engine** — APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM.
5. **Fake-breakout engine** — fake breaks enter the explicit reclaim path; true breaks block the setup.
6. **Multi-timeframe context** — higher/entry structure can filter and score an existing setup. Timestamp alignment prevents higher-timeframe look-ahead.
7. **Setup scoring** — transparent 0-100 heuristic quality score; never treated as win probability.
8. **Risk/backtest** — hypothetical SL/TP planning and sequential historical simulation.
9. **Execution simulation** — optional spread, commission, slippage, latency, session and precision effects, isolated from strategy decisions.
10. **Research validation** — chronological splits, R-based metrics, profit factor, drawdown and bootstrap expectancy uncertainty.
11. **Walk-forward validation** — expanding-history, rolling out-of-sample windows with hard test boundaries.
12. **Realtime data** — closed-candle monitoring with duplicate suppression and nearest-zone selection.
13. **Paper session** — next-bar paper entry, lifecycle management, and append-only event journaling.
14. **Integration facade** — `strategy.pipeline.run_research()` connects the core research stages into one consistent API.

## Key modules

- `strategy/candles.py` — candle structure and descriptive pressure.
- `strategy/levels.py` — legacy detector kept for compatibility.
- `strategy/levels_v2.py` — primary confirmed-swing zones.
- `strategy/market_structure.py` — HH/HL/LH/LL structural context.
- `strategy/sequence.py` — primary two-setup multi-candle logic.
- `strategy/fake_breakout.py` — breakout/reclaim classification.
- `strategy/protection.py` — level safety checks.
- `strategy/timeframe.py` — adaptive distances for 1m through 1D.
- `strategy/mtf.py` — structural context and timestamp alignment.
- `strategy/scoring.py` — explainable setup quality score.
- `strategy/engine.py` — central LONG/SHORT/WAIT strategy interface.
- `strategy/risk.py` — hypothetical risk plans and baseline exit simulation.
- `strategy/backtest.py` — sequential backtest plus bounded research windows, explicit entry timing, and optional MTF/execution integration.
- `strategy/execution.py` — research-only execution-friction simulation.
- `strategy/validation.py` — research metrics and chronological validation tools.
- `strategy/walk_forward.py` — rolling out-of-sample research windows.
- `strategy/pipeline.py` — high-level end-to-end research facade.
- `strategy/realtime.py` — closed-candle realtime monitor.
- `strategy/paper.py` — deterministic single-position paper simulator.
- `strategy/paper_session.py` — realtime-to-paper orchestration with next-bar entry and idempotency.
- `strategy/journal.py` — SIGNAL/OPEN/CLOSE research event journal.
- `adapters/mt5_feed.py` — read-only MT5 market-data adapter.

## System flow

```text
OHLC / MT5 closed bars
        |
        v
Timeframe normalization
        |
        v
Confirmed S/R zones <---- Market Structure
        |
        v
Core Sequence Engine
APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM
        |
        +---- Fake Breakout protection
        +---- MTF context / look-ahead protection
        +---- Setup scoring
        |
        v
LONG / SHORT / WAIT
        |
        +---- Historical path -> Risk -> Backtest -> Validation
        |
        +---- Realtime path -> Supervisor -> Paper Session -> Journal
        |
        v
Walk-forward / Out-of-sample research
```

The realtime path uses the same strategy engine rather than a separate live strategy:

`MT5 terminal -> MT5BarFeed -> RealtimeMonitor -> engine -> LONG/SHORT/WAIT -> Supervisor -> PaperSessionRunner`

The MT5 adapter is read-only. It does not call `order_send()`.

## Timestamp-aligned MTF

`build_timestamp_aligned_mtf_context()` accepts timestamped OHLC candles and a signal-candle close timestamp. A candle is usable only when:

`candle_open_time + timeframe_duration <= entry_timestamp`

This prevents a still-forming 1h/4h/1D candle from influencing a lower-timeframe historical decision. `run_backtest()` can inject this aligned context into scoring.

## Integrated research API

Use `strategy.pipeline.run_research()` when a single coherent result is preferred. It performs:

1. sequential strategy backtest;
2. optional execution-friction simulation;
3. descriptive research metrics;
4. chronological train/validation/out-of-sample split;
5. bootstrap expectancy uncertainty interval.

For rolling out-of-sample validation, use `strategy.walk_forward.walk_forward_backtest()`. This is an expanding-history evaluation tool, not a parameter optimizer or a claim of future profitability.

The components remain separately callable for unit testing and research experiments.

## Backtest entry timing

`run_backtest()` exposes an explicit `entry_timing` parameter:

- `signal_reference` — preserves the original historical assumption and uses the strategy confirmation reference on the signal candle.
- `next_bar_open` — fills at the next candle's open and begins exit monitoring only after that fill candle, matching the paper-session lifecycle.

The default remains `signal_reference` for backward compatibility. For research intended to mirror the realtime paper path, use `next_bar_open` consistently in both `run_backtest()` and `walk_forward_backtest()`.

## Backtest and execution assumptions

- Only closed historical information is used to construct zones and structure.
- Confirmed swings require right-side confirmation candles.
- A signal requires a separate reaction/test and confirmation sequence.
- Historical backtest entry timing is explicit; the legacy default is the signal reference, while paper-session-compatible research uses next-bar open.
- Paper-session entry from a realtime signal uses the next bar's open.
- Stop is beyond the reaction zone by an adaptive buffer.
- Default target is 2R.
- One hypothetical paper position is allowed at a time.
- If stop and target are both touched in one OHLC candle, stop is assumed first.
- Execution simulation is optional and separate from strategy logic.
- Commission is represented in price units rather than account currency.
- No broker order is submitted anywhere in the repository.

## Walk-forward validation

`walk_forward_backtest()` repeatedly evaluates non-overlapping test windows. Each fold retains all earlier candles as history, while strategy decisions inside the test window only see candles available before each decision. Exit simulation is capped at the fold boundary, preventing a trade in one OOS window from consuming future observations in another window. The same explicit `entry_timing` option is propagated into each fold.

This reduces a common validation mistake: reporting performance from a full-sample backtest as though it were untouched future data. Walk-forward evaluation is still historical evidence, not proof of profitability.

## Paper monitoring

The paper session runner is deliberately non-ordering. It records each evaluated signal, fills approved signals at the next bar's open, manages the existing position before evaluating a new entry opportunity, and ignores duplicate/old candles. Journal events are append-only and can be exported as plain dictionaries for later analysis.

## Validation

The validation layer is deliberately descriptive. It reports historical behavior; it does not prove future profitability. Parameter selection should be performed on training data, checked on validation data, and finally evaluated on untouched out-of-sample data. Robustness checks should include multiple time periods, execution-cost assumptions, and conservative OHLC ambiguity handling.

## Testing

The `tests/` directory covers candle/zone behavior, sequence logic, fake-breakout protection, market structure, MTF look-ahead protection, scoring, risk, baseline and realistic execution simulation, bounded backtesting, entry-timing semantics, validation, walk-forward windows, realtime state handling, paper trading, paper-session lifecycle, journaling, and the integrated research facade.

## Version / continuation protocol

Current version: **0.9.1**.

At the start of a new chat:

1. Read `VERSION.md` and this README.
2. Inspect latest Git history and GitHub Actions status.
3. Identify the current milestone and unfinished work.
4. Continue existing modules instead of recreating them.
5. Any behavior change gets a test or an explicit reason why a test is impractical.
6. Update the version only when the change matches semantic-versioning rules.

## Important

This repository is for programming practice and historical/realtime market-data research. It does not establish that a strategy is profitable. It is intentionally read-only with respect to MT5 trading actions. Any future execution architecture must remain isolated from the research engine and should only be considered after robust out-of-sample validation.
