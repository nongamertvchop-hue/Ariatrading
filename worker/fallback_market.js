/**
 * Synthetic market-data fallback for UI/research mode only.
 *
 * This module is deliberately deterministic within each closed-candle bucket so
 * browser polling does not invent a different market on every request.
 * It must never be presented as broker/live data.
 */

const BASE_PRICE = Object.freeze({
  "EUR/USD": 1.08500,
  "GBP/USD": 1.27000,
  "USD/JPY": 147.500,
  "AUD/USD": 0.66000,
  "USD/CAD": 1.35500,
});

export const FALLBACK_SOURCE = "synthetic-fallback";

export const TIMEFRAME_SECONDS = Object.freeze({
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "30m": 1800,
  "1h": 3600,
  "4h": 14400,
  "1D": 86400,
});

function tickPrice(base, bucket) {
  const wave = Math.sin(bucket * 0.73) * base * 0.00035;
  const drift = Math.cos(bucket * 0.17) * base * 0.00010;
  return base + wave + drift;
}

export function fallbackCandles(symbol, timeframe, count = 100, nowMs = Date.now()) {
  const step = TIMEFRAME_SECONDS[timeframe];
  if (!step) throw new Error(`unsupported timeframe: ${timeframe}`);
  const base = BASE_PRICE[symbol] ?? 1.0;
  const closedBucket = Math.floor(nowMs / 1000 / step) - 1;
  const candles = [];

  for (let i = count - 1; i >= 0; i -= 1) {
    const bucket = closedBucket - i;
    const open = tickPrice(base, bucket);
    const close = tickPrice(base, bucket + 0.46);
    const wick = Math.max(Math.abs(close - open) * 0.55, base * 0.00012);
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick;
    candles.push({
      datetime: new Date((bucket + 1) * step * 1000).toISOString(),
      open: Number(open.toFixed(6)),
      high: Number(high.toFixed(6)),
      low: Number(low.toFixed(6)),
      close: Number(close.toFixed(6)),
    });
  }
  return candles;
}

export function fallbackPrice(symbol, timeframe = "15m", nowMs = Date.now()) {
  const candles = fallbackCandles(symbol, timeframe, 2, nowMs);
  return candles[candles.length - 1].close;
}
