// Canonical live market-data endpoint for the Webaria chart.
// This endpoint never fabricates candles. Provider failure is surfaced as 503.

const CONFIG = Object.freeze({
  "1m": { interval: "1min", seconds: 60 },
  "5m": { interval: "5min", seconds: 300 },
  "15m": { interval: "15min", seconds: 900 },
  "30m": { interval: "30min", seconds: 1800 },
  "1h": { interval: "1h", seconds: 3600 },
  "4h": { interval: "4h", seconds: 14400 },
  "1D": { interval: "1day", seconds: 86400 },
});

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
    },
  });
}

function validateCandle(raw) {
  const candle = {
    datetime: String(raw.datetime || ""),
    open: Number(raw.open),
    high: Number(raw.high),
    low: Number(raw.low),
    close: Number(raw.close),
  };

  if (![candle.open, candle.high, candle.low, candle.close].every(Number.isFinite)) {
    throw new Error("provider returned invalid OHLC");
  }
  if (
    candle.high < Math.max(candle.open, candle.close)
    || candle.low > Math.min(candle.open, candle.close)
    || candle.high < candle.low
  ) {
    throw new Error("provider returned invalid OHLC relationship");
  }
  return candle;
}

async function fetchMarket(symbol, timeframe, apiKey) {
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

    const values = payload.values.map(validateCandle);
    if (values.length < 21) throw new Error("provider returned too few candles");

    // Twelve Data returns newest first. Keep the current forming candle
    // separate from completed history so strategy code never gets look-ahead.
    const liveCandle = values[0];
    const completed = values.slice(1, 101).reverse();

    return {
      candles: completed,
      live_candle: liveCandle,
      price: liveCandle.close,
      source: "twelve-data",
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = (url.searchParams.get("timeframe") || "15m").trim();

  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
    return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);
  }
  if (!Object.prototype.hasOwnProperty.call(CONFIG, timeframe)) {
    return json({ error: "bad_request", message: `unsupported timeframe: ${timeframe}` }, 400);
  }

  const apiKey = context.env?.TWELVE_DATA_API_KEY;
  if (!apiKey) {
    return json({
      error: "live_data_unavailable",
      message: "TWELVE_DATA_API_KEY is not configured",
      symbol,
      timeframe,
      source: "unavailable",
      execution: "NONE",
    }, 503);
  }

  try {
    const market = await fetchMarket(symbol, timeframe, apiKey);
    return json({
      symbol,
      timeframe,
      ...market,
      candles_used: market.candles.length,
      generated_at: new Date().toISOString(),
      execution: "NONE",
    });
  } catch (error) {
    return json({
      error: "live_data_unavailable",
      message: error?.message || "market data provider unavailable",
      symbol,
      timeframe,
      source: "unavailable",
      execution: "NONE",
    }, 503);
  }
}
