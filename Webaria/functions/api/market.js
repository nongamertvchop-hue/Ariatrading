// Canonical live market-data endpoint for Webaria.
// MT5 runtime is the source of truth. This edge function never fabricates candles
// and never falls back to a second market provider, preventing chart/strategy drift.

const TIMEFRAMES = new Set(["1m", "5m", "15m", "30m", "1h", "4h", "1D"]);

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
      "x-webaria-market-contract": "mt5-runtime-v6",
      ...extraHeaders,
    },
  });
}

function validateCandle(raw) {
  const rawTime = raw?.datetime ?? raw?.time;
  const datetime = typeof rawTime === "number"
    ? new Date((Math.abs(rawTime) < 1e11 ? rawTime * 1000 : rawTime)).toISOString()
    : String(rawTime || "");
  const parsed = Date.parse(datetime);
  const candle = {
    datetime,
    time: Number.isFinite(parsed) ? Math.floor(parsed / 1000) : NaN,
    open: Number(raw?.open),
    high: Number(raw?.high),
    low: Number(raw?.low),
    close: Number(raw?.close),
  };
  if (!candle.datetime || !Number.isFinite(candle.time) || ![candle.open, candle.high, candle.low, candle.close].every(Number.isFinite)) {
    throw new Error("runtime returned invalid OHLC");
  }
  if (candle.high < Math.max(candle.open, candle.close) || candle.low > Math.min(candle.open, candle.close) || candle.high < candle.low) {
    throw new Error("runtime returned invalid OHLC relationship");
  }
  return candle;
}

function normalizeRuntimePayload(payload, symbol, timeframe) {
  if (!payload || payload.source !== "mt5" || payload.execution !== "NONE") {
    throw new Error("runtime market contract rejected");
  }
  if (typeof payload.market_fingerprint !== "string" || !/^[0-9a-f]{64}$/.test(payload.market_fingerprint)) {
    throw new Error("runtime market fingerprint rejected");
  }
  if (!Array.isArray(payload.candles) || payload.candles.length < 21) {
    throw new Error("runtime returned too few completed candles");
  }
  const candles = payload.candles.map(validateCandle);
  for (let i = 1; i < candles.length; i += 1) {
    if (candles[i].time <= candles[i - 1].time) {
      throw new Error("runtime candles are not strictly chronological");
    }
  }
  const live = validateCandle(payload.live_candle);
  if (live.time <= candles.at(-1).time) {
    throw new Error("runtime forming candle must be newer than completed history");
  }
  const price = Number(payload.price);
  if (!Number.isFinite(price) || price <= 0) throw new Error("runtime returned invalid price");
  return {
    symbol,
    timeframe,
    candles: candles.map(({ time: _time, ...candle }) => candle),
    live_candle: (({ time: _time, ...candle }) => candle)(live),
    price,
    tick: payload.tick || null,
    source: "mt5",
    market_fingerprint: payload.market_fingerprint,
    candles_used: candles.length,
    generated_at: new Date().toISOString(),
    runtime_generated_at: payload.generated_at || null,
    execution: "NONE",
  };
}

export async function onRequestGet(context) {
  const requestUrl = new URL(context.request.url);
  const symbol = (requestUrl.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = (requestUrl.searchParams.get("timeframe") || "15m").trim();

  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
    return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);
  }
  if (!TIMEFRAMES.has(timeframe)) {
    return json({ error: "bad_request", message: `unsupported timeframe: ${timeframe}` }, 400);
  }

  const runtimeUrl = String(context.env?.MT5_RUNTIME_API_URL || "").trim().replace(/\/$/, "");
  if (!runtimeUrl) {
    return json({ error: "live_data_unavailable", message: "MT5_RUNTIME_API_URL is not configured", symbol, timeframe, source: "unavailable", execution: "NONE" }, 503);
  }

  const token = String(context.env?.RUNTIME_API_TOKEN || "").trim();
  if (!token) {
    return json({ error: "live_data_unavailable", message: "RUNTIME_API_TOKEN is not configured", symbol, timeframe, source: "unavailable", execution: "NONE" }, 503);
  }

  const target = new URL(`${runtimeUrl}/market`);
  target.searchParams.set("symbol", symbol.replace("/", ""));
  target.searchParams.set("timeframe", timeframe);
  target.searchParams.set("count", "100");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(target, {
      signal: controller.signal,
      headers: { accept: "application/json", authorization: `Bearer ${token}`, "cache-control": "no-cache" },
    });
    let payload;
    try { payload = await response.json(); } catch { throw new Error(`runtime returned invalid JSON (HTTP ${response.status})`); }
    if (!response.ok) throw new Error(payload?.message || `runtime HTTP ${response.status}`);
    return json(normalizeRuntimePayload(payload, symbol, timeframe));
  } catch (error) {
    return json({
      error: "live_data_unavailable",
      message: error?.name === "AbortError" ? "MT5 runtime request timed out" : (error?.message || "MT5 runtime unavailable"),
      symbol,
      timeframe,
      source: "unavailable",
      execution: "NONE",
    }, 503);
  } finally {
    clearTimeout(timer);
  }
}
