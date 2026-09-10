// Webaria strategy adapter for MT5-backed market data.
// The browser supplies candles already obtained from /api/market, so strategy
// evaluation cannot silently switch to another market-data provider.
import { evaluatePriceAction } from "./signal.js";

const TIMEFRAMES = new Set(["1m", "5m", "15m", "30m", "1h", "4h", "1D"]);

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function finite(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${name} is invalid`);
  return number;
}

function normalizeCandle(raw) {
  if (!raw || typeof raw !== "object") throw new Error("candle must be an object");
  const candle = {
    open: finite(raw.open, "open"),
    high: finite(raw.high, "high"),
    low: finite(raw.low, "low"),
    close: finite(raw.close, "close"),
    datetime: String(raw.datetime ?? raw.time ?? ""),
  };
  if (
    candle.high < Math.max(candle.open, candle.close)
    || candle.low > Math.min(candle.open, candle.close)
    || candle.high < candle.low
  ) throw new Error("invalid OHLC relationship");
  return candle;
}

export async function onRequestPost(context) {
  try {
    const payload = await context.request.json();
    const symbol = String(payload?.symbol || "").trim().toUpperCase();
    const timeframe = String(payload?.timeframe || "").trim();
    const candles = Array.isArray(payload?.candles) ? payload.candles.map(normalizeCandle) : [];

    if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
      return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);
    }
    if (!TIMEFRAMES.has(timeframe)) {
      return json({ error: "bad_request", message: `unsupported timeframe: ${timeframe}` }, 400);
    }
    if (candles.length < 20) {
      return json({ error: "bad_request", message: "at least 20 completed candles are required" }, 400);
    }

    const signal = evaluatePriceAction(candles, timeframe);
    return json({
      symbol,
      timeframe,
      price: candles.at(-1)?.close ?? null,
      ...signal,
      candles,
      candles_used: candles.length,
      source: "mt5",
      execution: "NONE",
      generated_at: new Date().toISOString(),
    });
  } catch (error) {
    return json({ error: "bad_request", message: error?.message || "invalid strategy request" }, 400);
  }
}
