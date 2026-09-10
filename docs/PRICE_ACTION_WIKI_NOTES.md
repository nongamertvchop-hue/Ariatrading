# ARIA Price Action — Wiki Research Notes

## Purpose

This document records the external reference material used to improve Ariatrading's indicator-free price-action logic. It is a research input, not a claim that any setup is profitable.

## Sources

1. Wikipedia — **Candlestick chart**
   https://en.wikipedia.org/wiki/Candlestick_chart

   Key points used:
   - A standard candlestick represents open, high, low, and close for a time interval.
   - The real body is the distance between open and close.
   - The upper/lower shadows (wicks) show the high/low excursions.
   - Candle color/direction is a presentation convention; it should not by itself be treated as an order instruction.

2. Wikipedia — **Technical analysis**
   https://en.wikipedia.org/wiki/Technical_analysis

   Key points used:
   - Support and resistance are core price-based concepts.
   - A trend describes persistent directional movement.
   - A breakout is a penetration of a prior support/resistance area.
   - A trendline is based on price peaks/troughs rather than an indicator requirement.

3. Wikipedia — **Support and resistance**
   https://en.wikipedia.org/wiki/Support_and_resistance

   Key points used:
   - Support/resistance can be treated as price areas rather than one exact tick.
   - Repeated tests can make a level more significant.
   - A broken support can later behave as resistance, and vice versa.
   - Breaks should be distinguished from ordinary tests/rejections.

4. Wikipedia — **Price action trading**
   https://en.wikipedia.org/wiki/Price_action_trading

   Key points used:
   - Price action focuses on price movement itself rather than depending on technical indicators.
   - This fits ARIA's original naked-chart design goal.

## Implementation decisions

### 1. Completed candles only

The strategy consumes completed candles and excludes the currently forming candle from the decision set. This prevents a signal from changing merely because the live candle is still moving and reduces look-ahead/data-leakage risk.

### 2. Structure first

The signal gate first evaluates market structure using confirmed swing highs/lows:

- Bullish structure: higher highs + higher lows (HH + HL)
- Bearish structure: lower highs + lower lows (LH + LL)
- Mixed structure: RANGE/UNKNOWN → no directional signal

### 3. Zone-based support/resistance

Support and resistance are represented as zones derived from recent swing prices and an OHLC-derived adaptive tolerance. The system does not assume a single exact price level is always meaningful.

### 4. Confirmation candle

A directional setup requires the latest completed confirmation candle to show directional pressure:

- LONG: bullish close with close positioned near the upper part of the candle range
- SHORT: bearish close with close positioned near the lower part of the candle range

A rejection wick on the tested side is additional evidence, not an independent order command.

### 5. Fake-breakout protection

A test that pierces a support/resistance area intrabar but closes back inside/through the zone is classified as a possible fake breakout and requires confirmation before any directional signal is allowed.

A decisive close beyond the zone blocks the old counter-trend setup instead of treating the broken level as an immediate reversal signal.

### 6. Signal policy

The strategy returns `LONG`, `SHORT`, or `WAIT`.

`WAIT` is intentional when structure, zone interaction, breakout state, or confirmation is incomplete. The system must prefer missing a setup over inventing certainty from weak evidence.

## Research caveat

Candlestick patterns and technical-analysis concepts are heuristics. They can fail, and historical pattern recognition does not guarantee future returns. The Ariatrading implementation therefore treats these concepts as deterministic rules for research/paper testing, not as proof of profitability.

## Safety boundary

This strategy layer is **paper/research only**. `execution` remains `NONE` and the web terminal must not forward these signals to a live broker.
