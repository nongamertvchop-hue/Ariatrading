# Web ↔ MT5 single-source contract

## Problem fixed
The web application had multiple market paths. `/api/market` already treated the MT5 bridge as authoritative, while the signal adapter could use another market provider. That can make the displayed chart, quote, and signal refer to different candles.

## Contract

`MT5 terminal -> /api/mt5/ingest -> Mt5MarketStore -> /api/market + /api/signal -> Webaria`

`/api/signal` must not fetch a second market provider. When the MT5 market store is unavailable, stale, malformed, or violates the realtime feed contract, the endpoint fails closed instead of substituting another price source.

## Browser behavior

`Webaria/live-market.js` polls `/api/market`, renders the MT5 quote/candles, then asks `/api/signal` for strategy analysis. Both responses therefore originate from the same MT5 market store.

The browser does not treat the forming candle as the strategy input. Strategy evaluation uses completed candles returned by the market store, while the forming candle is display context only.

## Operational meaning

A green browser `MT5 LIVE · STRATEGY LIVE` state means the MT5 bridge supplied acceptable broker data to the Webaria market store and the signal endpoint accepted the same completed-candle stream. It does not mean a broker order was placed. Execution remains separate and the supported runtime is PAPER/DEMO only.
