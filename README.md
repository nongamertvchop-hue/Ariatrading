# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

**Current version: 0.8.0**

## Core idea

Ariatrading deliberately starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No chart indicators are required. The model works from OHLC candles and horizontal support/resistance zones.

## Architecture

The project is layered around the two core setups rather than adding many unrelated entry patterns:

1. **Market structure** — confirmed swing highs/lows are labeled HH, HL, LH and LL, producing a simple bullish/bearish/range/unknown bias.
2. **Zone intelligence** — repeated confirmed swings form support/resistance zones.
3. **Candle intelligence** — completed candles are classified by simple buying/selling pressure.
4. **Sequence engine** — APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM.
5. **Fake-breakout engine** — the sequence engine uses the breakout classifier, so a fake break becomes an explicit RECLAIM path.
6. **Multi-timeframe context** — higher and entry timeframe structures can be supplied to describe directional alignment. Timestamp-aligned context uses only candles whose full intervals have closed.
7. **Setup scoring** — transparent 0-100 heuristic components rank zone quality, structure, breakout behavior, confirmation and MTF alignment. A score is **not** a win probability.
8. **Risk/backtest** — hypothetical stop/target planning and sequential historical simulation, including timestamp-aligned MTF scoring.
9. **Research validation** — chronological train/validation/out-of-sample splitting plus descriptive R-based metrics and uncertainty estimates.
10. **Execution simulation** — optional historical spread, commission, slippage, latency, session and price-precision frictions, kept separate from strategy decisions.
11. **Realtime data layer** — a feed interface and MT5 adapter can continuously read live market data while the strategy evaluates only completed candles.

### Key modules

- `strategy/candles.py` — candle structure and simple buying/selling pressure.
- `strategy/levels.py` — original support/resistance detector kept for compatibility.
- `strategy/levels_v2.py` — confirmed swing-based support/resistance zones.
- `strategy/market_structure.py` — confirmed-swing HH/HL/LH/LL market structure.
- `strategy/sequence.py` — multi-candle setup sequence with integrated fake-breakout state.
- `strategy/fake_breakout.py` — conservative breakout classification.
- `strategy/protection.py` — danger/broken protection around levels.
- `strategy/timeframe.py` — adaptive price distances for 1m, 5m, 15m, 30m, 1h, 4h and 1D.
- `strategy/mtf.py` — multi-timeframe structural context, timestamp alignment and lookahead protection.
- `strategy/scoring.py` — explainable setup-quality score.
- `strategy/engine.py` — unified LONG/SHORT/WAIT interface with structure and optional MTF score.
- `strategy/risk.py` — hypothetical stop/target planning and conservative exit simulation.
- `strategy/backtest.py` — sequential historical backtest, R-multiple statistics and timestamp-aligned MTF integration.
- `strategy/validation.py` — chronological splits, descriptive research metrics, profit factor, drawdown and bootstrap expectancy intervals.
- `strategy/execution.py` — conservative execution-friction simulation; no broker actions.
- `strategy/realtime.py` — closed-candle realtime monitoring with duplicate-bar suppression and nearest-zone selection.
- `adapters/mt5_feed.py` — read-only MetaTrader 5 market-data adapter.
- `requirements-realtime.txt` — optional dependency for MT5 realtime data access.

## Realtime market-data design

The realtime layer is deliberately separated from the strategy engine:

`MT5 terminal -> MT5BarFeed -> RealtimeMonitor -> existing strategy engine -> LONG/SHORT/WAIT`

The MT5 Python integration can retrieve the current tick and historical bars from a connected terminal. For strategy evaluation, Ariatrading requests bars starting at position 1, because MT5 position 0 is the currently forming candle. Therefore an in-progress candle is never treated as a confirmed signal candle. The monitor also records the latest evaluated bar timestamp and will not evaluate the same closed candle twice.

Realtime zone construction uses the timeframe's adaptive zone tolerance and chooses the nearest relevant support/resistance zone instead of assuming the last returned zone is the correct one.

Realtime monitoring is **read-only**. The code does not call `order_send()` and does not place trades.

## Timestamp-aligned MTF context

`build_timestamp_aligned_mtf_context()` accepts timestamped OHLC candles and an entry timestamp representing the close time of the signal candle. For every timeframe, a candle is included only when:

`candle_open_time + timeframe_duration <= entry_timestamp`

This matters because MT5 timestamps identify the candle's opening time. A higher-timeframe candle that has already opened can still be forming when a lower-timeframe setup occurs. Excluding it prevents higher-timeframe look-ahead bias.

`run_backtest()` can receive `mtf_candles_by_timeframe`. When this option is used, candle timestamps must be timezone-aware datetimes. The backtest derives the signal candle close timestamp from its timeframe and asks the MTF layer for only information available at that moment. If timestamps are absent, it fails closed rather than guessing.

## Research validation

The validation layer deliberately separates descriptive evaluation from strategy construction:

- chronological train/validation/test splits preserve time order;
- profit factor, expectancy in R, win rate and maximum drawdown summarize historical behavior;
- bootstrap expectancy intervals quantify uncertainty in the supplied sample;
- none of these metrics are forecasts or guarantees of future results.

## Execution simulation

`ExecutionModel` provides a research-only layer for testing how trading frictions change historical results:

- spread is applied through bid/ask effects;
- slippage shifts realized entry/exit prices;
- commission is represented in price units so the layer remains independent of account currency and position sizing;
- latency is modeled as skipped initial bars;
- optional session boundaries and price precision can be enforced;
- the original strategy, risk plan and broker adapter remain separate.

This is deliberately a simulation layer, not live execution.

## Backtest assumptions

- Zones are built only from candles already closed before the signal candle.
- Confirmed swings require their right-side confirmation candles, preventing future-data leakage inside the supplied history.
- A signal requires a separate test/reaction candle and confirmation candle.
- Entry reference is the confirmation candle close.
- Stop is placed beyond the reaction zone by an adaptive distance.
- Default target is 2R, configurable for research.
- One hypothetical position is allowed at a time.
- If one candle touches both stop and target, the simulator assumes the stop happened first because OHLC data does not reveal intrabar order.
- Optional MTF context is timestamp-aligned and cannot use a higher-timeframe candle that was still forming at entry.
- Execution friction simulation is optional and separate from the baseline backtest.

## Testing

The `tests/` directory covers candle/level behavior plus sequence, fake-breakout protection, timeframe utilities, market structure, multi-timeframe context, timestamp lookahead protection, setup scoring, backtesting, research validation, execution frictions, risk/exit simulation, and realtime feed behavior including duplicate-bar suppression and nearest-zone selection.

## Continuation protocol

At the start of a new chat:

1. Read `VERSION.md` and this `README.md`.
2. Inspect the latest Git history.
3. Identify the current milestone and unfinished work.
4. Continue from the existing implementation; do not recreate completed modules.
5. Any behavior change must have a test or a clear reason why a test is not practical.
6. Update `VERSION.md` after a meaningful strategy/architecture milestone.

## Important

This repository is for programming practice and historical/realtime market-data research. It does not establish that a strategy is profitable and it does not place live orders. Timeframe parameters are engineering defaults, not proven optimal values. Any future optimization should use separate training/validation/out-of-sample data to reduce overfitting. Before any execution integration, the backtest must also model realistic spread, commission, slippage, latency and symbol-specific price precision.
