# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

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
5. **Fake-breakout engine** — the sequence engine now uses the same breakout classifier, so a fake break becomes an explicit RECLAIM path instead of a disconnected filter.
6. **Multi-timeframe context** — higher and entry timeframe structures can be supplied to describe directional alignment. This is context, not a new entry setup.
7. **Setup scoring** — transparent 0-100 heuristic components rank zone quality, structure, breakout behavior, confirmation and MTF alignment. A score is **not** a win probability.
8. **Risk/backtest** — hypothetical stop/target planning and sequential historical simulation.

### Key modules

- `strategy/candles.py` — candle structure and simple buying/selling pressure.
- `strategy/levels.py` — original support/resistance detector kept for compatibility.
- `strategy/levels_v2.py` — confirmed swing-based support/resistance zones.
- `strategy/market_structure.py` — confirmed-swing HH/HL/LH/LL market structure.
- `strategy/sequence.py` — multi-candle setup sequence with integrated fake-breakout state.
- `strategy/fake_breakout.py` — conservative breakout classification.
- `strategy/protection.py` — danger/broken protection around levels.
- `strategy/timeframe.py` — adaptive price distances for 1m, 5m, 15m, 30m, 1h, 4h and 1D.
- `strategy/mtf.py` — multi-timeframe structural context and alignment.
- `strategy/scoring.py` — explainable setup-quality score.
- `strategy/engine.py` — unified LONG/SHORT/WAIT interface with structure and optional MTF score.
- `strategy/risk.py` — hypothetical stop/target planning and conservative exit simulation.
- `strategy/backtest.py` — sequential historical backtest and R-multiple statistics.

## Design principle

The system should answer **"What did price actually do?"** before answering **"Should this setup be considered?"**. Indicators are intentionally excluded from the core logic. Additional modules should strengthen the evidence for the same two setups rather than create an ever-growing list of entry patterns.

## Backtest assumptions

- Zones are built only from candles already closed before the signal candle.
- Confirmed swings require their right-side confirmation candles, preventing future-data leakage inside the supplied history.
- A signal requires a separate test/reaction candle and confirmation candle.
- Entry reference is the confirmation candle close.
- Stop is placed beyond the reaction zone by an adaptive distance.
- Default target is 2R, configurable for research.
- One hypothetical position is allowed at a time.
- If one candle touches both stop and target, the simulator assumes the stop happened first because OHLC data does not reveal intrabar order.
- No spread, commission, slippage, news filter, or execution latency is modeled yet.

## Testing

The `tests/` directory covers candle/level behavior plus sequence, fake-breakout protection, timeframe utilities, market structure, multi-timeframe context, setup scoring, backtesting, and risk/exit simulation.

## Important

This repository is for programming practice and historical research. It does not establish that a strategy is profitable and it does not place live orders. Timeframe parameters are engineering defaults, not proven optimal values. Any future optimization should use separate training/validation/out-of-sample data to reduce overfitting. Before any execution integration, the backtest must also model realistic spread, commission, slippage, latency and symbol-specific price precision.
