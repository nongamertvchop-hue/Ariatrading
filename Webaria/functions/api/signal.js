// Webaria Pages compatibility endpoint.
// The Worker deployment already provides /api/signal. This Pages Function keeps
// the standalone Pages deployment from losing its chart when that Worker is
// not the process serving the site.

const CONFIG = Object.freeze({
  "1m": { interval: "1min", seconds: 60 },
  "5m": { interval: "5min", seconds: 300 },
  "15m": { interval: "15min", seconds: 900 },
  "30m": { interval: "30min", seconds: 1800 },
  "1h": { interval: "1h", seconds: 3600 },
  "4h": { interval: "4h", seconds: 14400 },
  "1D": { interval: "1day", seconds: 86400 },
});

const BASE_PRICE = Object.freeze({
  "EUR/USD": 1.08500,
  "GBP/USD": 1.27000,
  "USD/JPY": 147.500,
  "AUD/USD": 0.66000,
  "USD/CAD": 1.35500,
});

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

function validateCandle(raw) {
  const candle = {
    open: finite(raw.open, "open"),
    high: finite(raw.high, "high"),
    low: finite(raw.low, "low"),
    close: finite(raw.close, "close"),
    datetime: String(raw.datetime || ""),
  };
  if (candle.high < Math.max(candle.open, candle.close) || candle.low > Math.min(candle.open, candle.close) || candle.high < candle.low) {
    throw new Error("invalid OHLC relationship");
  }
  return candle;
}

async function fetchRealCandles(symbol, timeframe, apiKey) {
  const config = CONFIG[timeframe];
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol.replace("/", ""));
  url.searchParams.set("interval", config.interval);
  url.searchParams.set("outputsize", "100");
  url.searchParams.set("timezone", "UTC");
  url.searchParams.set("apikey", apiKey);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`provider HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || !Array.isArray(payload.values)) {
      throw new Error(payload.message || "invalid provider response");
    }

    const candles = payload.values
      .slice(1, 101) // never use the currently forming candle for strategy history
      .map(validateCandle)
      .reverse();
    if (candles.length < 10) throw new Error("not enough completed candles");
    return { candles, source: "twelve-data" };
  } finally {
    clearTimeout(timer);
  }
}

function fallbackCandles(symbol, timeframe, count = 100) {
  const step = CONFIG[timeframe].seconds;
  const base = BASE_PRICE[symbol] ?? 1.00000;
  const now = Math.floor(Date.now() / 1000 / step) * step;
  let price = base;
  const candles = [];

  // Deterministic fallback: same request bucket produces a stable chart instead
  // of a new random market on every poll, which otherwise makes the chart jump.
  for (let i = count; i > 0; i -= 1) {
    const bucket = Math.floor((now / step) - i);
    const wave = Math.sin(bucket * 0.73) * 0.00035;
    const drift = Math.cos(bucket * 0.17) * 0.00010;
    const direction = wave + drift;
    const open = price;
    const close = open + direction;
    const wick = Math.max(Math.abs(direction) * 0.45, base * 0.00015);
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick;
    candles.push({
      datetime: new Date((now - i * step) * 1000).toISOString(),
      open: Number(open.toFixed(6)),
      high: Number(high.toFixed(6)),
      low: Number(low.toFixed(6)),
      close: Number(close.toFixed(6)),
    });
    price = close;
  }
  return candles;
}

function fallbackSignal(candles) {
  const last = candles[candles.length - 1];
  return {
    signal: "WAIT",
    state: "APPROACH",
    reason: "Pages compatibility mode: strategy Worker unavailable",
    price: last.close,
    structure_bias: "UNKNOWN",
    zone: null,
    entry_reference: null,
    stop_reference: null,
    breakout_state: "NO_BREAKOUT",
    score: null,
  };
}

export async function onRequestGet(context) {
  try {
    const url = new URL(context.request.url);
    const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
    const timeframe = (url.searchParams.get("timeframe") || "15m").trim();

    if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);
    if (!Object.prototype.hasOwnProperty.call(CONFIG, timeframe)) return json({ error: "bad_request", message: `unsupported timeframe: ${timeframe}` }, 400);

    let candles;
    let source;
    if (context.env?.TWELVE_DATA_API_KEY) {
      try {
        ({ candles, source } = await fetchRealCandles(symbol, timeframe, context.env.TWELVE_DATA_API_KEY));
      } catch (_) {
        candles = fallbackCandles(symbol, timeframe);
        source = "pages-fallback";
      }
    } else {
      candles = fallbackCandles(symbol, timeframe);
      source = "pages-fallback";
    }

    const signal = fallbackSignal(candles);
    return json({
      symbol,
      timeframe,
      ...signal,
      candles,
      candles_used: candles.length,
      source,
      execution: "NONE",
      generated_at: new Date().toISOString(),
    });
  } catch (error) {
    return json({ error: "internal_error", message: error?.message || "unknown error" }, 500);
  }
}
