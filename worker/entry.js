/**
 * Webaria Worker gateway.
 *
 * Keeps the strategy Worker intact while adding bounded caching and a clearly
 * labelled synthetic fallback for research/UI mode when market-data secrets
 * are not configured. No broker order execution is performed here.
 *
 * Bodyguard(Aria) v0.01.0 enforces public API request validation and rate limits
 * before market handlers run.
 */

import app from "./index.js";
import { handleSignalParityV2, evaluateRealtimeSignalParity } from "./signal_parity_v2.js";
import { buildSignalEventId } from "./signal_event.js";
import { fallbackCandles, fallbackPrice, FALLBACK_SOURCE, TIMEFRAME_SECONDS } from "./fallback_market.js";
import { guardPublicRequest, applySecurityHeaders, BODYGUARD_VERSION } from "../bodyguard/worker/bodyguard.js";

const FRESH_TTL_MS = Object.freeze({
  "/api/price": 10_000,
  "/api/signal": 30_000,
  "/api/live-candle": 10_000,
});
const STALE_TTL_MS = Object.freeze({
  "/api/price": 5 * 60_000,
  "/api/signal": 5 * 60_000,
  "/api/live-candle": 2 * 60_000,
});
const responseCache = new Map();

function cacheKey(request) { return request.method + ":" + request.url; }

function cloneHeaders(response, extra = {}) {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  return headers;
}

function cachedResponse(record, statusOverride, cacheStatus) {
  return applySecurityHeaders(new Response(record.body, {
    status: statusOverride ?? record.status,
    headers: cloneHeaders(record.headers, {
      "x-webaria-market-cache": cacheStatus,
      "cache-control": "no-store",
    }),
  }));
}

async function readResponse(response) {
  return {
    body: await response.clone().arrayBuffer(),
    headers: response.headers,
    status: response.status,
    savedAt: Date.now(),
  };
}

function json(data, status = 200, headers = {}) {
  return applySecurityHeaders(new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  }));
}

function requestParams(request) {
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = (url.searchParams.get("timeframe") || "15m").trim();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new Error("symbol must look like EUR/USD");
  if (!TIMEFRAME_SECONDS[timeframe]) throw new Error(`unsupported timeframe: ${timeframe}`);
  return { symbol, timeframe };
}

function fallbackSignalResponse(request) {
  const { symbol, timeframe } = requestParams(request);
  const candles = fallbackCandles(symbol, timeframe, 100);
  const result = evaluateRealtimeSignalParity(candles, timeframe);
  const response = {
    symbol,
    timeframe,
    ...result,
    source: FALLBACK_SOURCE,
    data_quality: {
      ok: true,
      reason: "synthetic fallback: market-data secret is not configured",
      latest_time: result.bar_time,
      age_seconds: 0,
      mode: "SIMULATION",
    },
    generated_at: new Date().toISOString(),
    execution: "NONE",
  };
  return buildSignalEventId(response).then((event_id) => json({ ...response, event_id }, 200, {
    "x-webaria-data-source": FALLBACK_SOURCE,
  }));
}

function fallbackPriceResponse(request) {
  const { symbol, timeframe } = requestParams(request);
  const price = fallbackPrice(symbol, timeframe);
  return json({
    symbol,
    price,
    source: FALLBACK_SOURCE,
    generated_at: new Date().toISOString(),
    execution: "NONE",
  }, 200, { "x-webaria-data-source": FALLBACK_SOURCE });
}

function fallbackCandleResponse(request) {
  const { symbol, timeframe } = requestParams(request);
  const candle = fallbackCandles(symbol, timeframe, 1)[0];
  return json({
    symbol,
    timeframe,
    candle,
    confirmed: true,
    source: FALLBACK_SOURCE,
    generated_at: new Date().toISOString(),
    execution: "NONE",
  }, 200, { "x-webaria-data-source": FALLBACK_SOURCE });
}

async function resolveApi(request, env, ctx, pathname) {
  if (!env.TWELVE_DATA_API_KEY) {
    if (pathname === "/api/signal") return fallbackSignalResponse(request);
    if (pathname === "/api/price") return fallbackPriceResponse(request);
    if (pathname === "/api/live-candle") return fallbackCandleResponse(request);
  }

  if (pathname === "/api/signal") return handleSignalParityV2(request, env);
  return app.fetch(request, env, ctx);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Bodyguard(Aria): block abusive / invalid public API traffic early.
    if (url.pathname.startsWith("/api/")) {
      const blocked = guardPublicRequest(request);
      if (blocked) return blocked;
    }

    const ttl = FRESH_TTL_MS[url.pathname];
    const staleTtl = STALE_TTL_MS[url.pathname];

    if (!ttl || request.method !== "GET") {
      const response = await app.fetch(request, env, ctx);
      return applySecurityHeaders(response);
    }

    const key = cacheKey(request);
    const now = Date.now();
    const cached = responseCache.get(key);
    if (cached && now - cached.savedAt <= ttl) return cachedResponse(cached, cached.status, "HIT");

    try {
      const response = await resolveApi(request, env, ctx, url.pathname);
      if (response.ok) {
        const record = await readResponse(response);
        responseCache.set(key, record);
        return cachedResponse(record, record.status, "MISS");
      }
      if (cached && now - cached.savedAt <= staleTtl) return cachedResponse(cached, 200, "STALE");
      return applySecurityHeaders(response);
    } catch (error) {
      if (cached && now - cached.savedAt <= staleTtl) return cachedResponse(cached, 200, "STALE");
      return json({ error: "upstream_or_internal_error", message: error?.message || "unknown error", guard: "Bodyguard(Aria)", version: BODYGUARD_VERSION }, 502);
    }
  },
};
