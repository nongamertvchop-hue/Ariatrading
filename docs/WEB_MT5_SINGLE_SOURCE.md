# Web ↔ MT5 single-source contract

## Problem fixed

The web application had multiple market paths. `/api/market` already treated the MT5 bridge as authoritative, while the signal adapter could use Twelve Data and an older browser bridge called an unavailable `/api/strategy` route. That can make the displayed chart, quote, and signal refer to different candles.

## Contract

For LIVE market visualization and signal evaluation:

`MT5 terminal -> /api/mt5/ingest -> Mt5MarketStore -> /api/market + /api/signal -> Webaria`

`/api/signal` must not fetch a second market provider. When the MT5 market store is unavailable or stale, the endpoint fails closed instead of substituting another price source.

## Browser behavior

`Webaria/live-market.js` polls `/api/market`, renders the MT5 quote/candles, then asks `/api/signal` for strategy analysis. Both responses therefore originate from the same MT5 market store.

## Operational meaning

A green browser "LIVE" state means the MT5 bridge has supplied fresh broker data to the Webaria market store. It does not mean a broker order was placed. Execution remains controlled by the separate MT5 runtime safeguards.
