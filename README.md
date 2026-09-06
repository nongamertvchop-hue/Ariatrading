# Ariatrading

Educational price-action research project for EURUSD-style OHLC data.

## Core idea

The system starts with only two reversal setups:

- **LONG:** price approaches support -> tests support -> rejects/reclaims it -> bullish confirmation -> LONG.
- **SHORT:** price approaches resistance -> tests resistance -> rejects/reclaims it -> bearish confirmation -> SHORT.
- **WAIT:** the sequence is incomplete, ambiguous, or the level has clearly broken.

No chart indicators are required. The model works from OHLC candles and horizontal support/resistance zones.

## Current architecture

- `strategy/candles.py` — candle structure and simple buying/selling pressure.
- `strategy/levels.py` — original support/resistance detector.
- `strategy/levels_v2.py` — confirmed swing-based support/resistance zones.
- `strategy/sequence.py` — multi-candle APPROACH/TEST/RECLAIM-REJECT/CONFIRM logic.
- `strategy/fake_breakout.py` — conservative breakout classification.
- `strategy/protection.py` — danger/broken protection around levels.
- `strategy/timeframe.py` — adaptive price distances for 1m, 5m, 15m, 30m, 1h, 4h and 1D.
- `strategy/engine.py` — unified LONG/SHORT/WAIT decision interface.
- `strategy/risk.py` — hypothetical stop/target planning and conservative exit simulation.
- `strategy/backtest.py` — sequential historical backtest and R-multiple statistics.

## Backtest assumptions

- Zones are built only from candles already closed before the signal candle.
- A signal requires a separate test/reaction candle and confirmation candle.
- Entry reference is the confirmation candle close.
- Stop is placed beyond the reaction zone by an adaptive distance.
- Default target is 2R, configurable for research.
- One hypothetical position is allowed at a time.
- If one candle touches both stop and target, the simulator assumes the stop happened first because OHLC data does not reveal intrabar order.
- No spread, commission, slippage, news filter, or execution latency is modeled yet.

## Testing

The `tests/` directory covers candle/level behavior plus sequence, false-break protection, timeframe utilities, backtesting, and risk/exit simulation.

## Important

This repository is for programming practice and historical research. It does not establish that a strategy is profitable and it does not place live orders. Timeframe parameters are engineering defaults, not proven optimal values. Any future optimization should use separate training/validation/out-of-sample data to reduce overfitting.
