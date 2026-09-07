/**
 * Webaria Worker gateway.
 *
 * Keeps the existing strategy Worker intact while protecting upstream market
 * data from aggressive browser polling. Successful API responses are cached
 * briefly, and a recent successful response is served as a stale snapshot when
 * Twelve Data temporarily returns a quota/network/provider error.
 *
 * This layer never changes LONG/SHORT/WAIT semantics and never executes orders.
 */

import app from "./index.js";

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

function cacheKey(request) {
  return request.method + ":" + request.url;
}

function cloneHeaders(response, extra = {}) {
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  return headers;
}

function cachedResponse(record, statusOverride, cacheStatus) {
  return new Response(record.body, {
    status: statusOverride ?? record.status,
    headers: cloneHeaders(record.headers, {
      "x-webaria-market-cache": cacheStatus,
      "cache-control": "no-store",
    }),
  });
}

async function readResponse(response) {
  return {
    body: await response.clone().arrayBuffer(),
    headers: response.headers,
    status: response.status,
    savedAt: Date.now(),
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const ttl = FRESH_TTL_MS[url.pathname];
    const staleTtl = STALE_TTL_MS[url.pathname];

    if (!ttl || request.method !== "GET") return app.fetch(request, env, ctx);

    const key = cacheKey(request);
    const now = Date.now();
    const cached = responseCache.get(key);
    if (cached && now - cached.savedAt <= ttl) {
      return cachedResponse(cached, cached.status, "HIT");
    }

    try {
      const response = await app.fetch(request, env, ctx);
      if (response.ok) {
        const record = await readResponse(response);
        responseCache.set(key, record);
        return cachedResponse(record, record.status, "MISS");
      }

      if (cached && now - cached.savedAt <= staleTtl) {
        return cachedResponse(cached, 200, "STALE");
      }
      return response;
    } catch (error) {
      if (cached && now - cached.savedAt <= staleTtl) {
        return cachedResponse(cached, 200, "STALE");
      }
      throw error;
    }
  },
};
