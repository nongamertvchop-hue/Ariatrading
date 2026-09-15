# Indicator direction confirmation

The strategy keeps Price Action as the setup generator and uses indicators as a directional confirmation gate.

## LONG

A Price Action LONG setup is allowed only when all available directional checks agree:

- EMA20 > EMA50
- RSI14 >= 50
- MACD histogram >= 0
- EMA50 > EMA200 when EMA200 is warmed up

## SHORT

A Price Action SHORT setup is allowed only when all available directional checks agree:

- EMA20 < EMA50
- RSI14 <= 50
- MACD histogram <= 0
- EMA50 < EMA200 when EMA200 is warmed up

ADX14 is not directional. It adds confirmation strength when the trend is moderate/strong.

If indicator warm-up is incomplete, or any available directional check conflicts with the Price Action direction, the engine returns WAIT. Indicators never create a third direction.

All calculations use completed candles only, so the confirmation layer remains causal and compatible with chronological backtests.
