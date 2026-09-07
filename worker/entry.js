/**
 * Webaria Worker gateway.
 *
 * Keeps the existing market-data cache while adding a persistent control plane
 * for the MT5 demo runtime. This Worker never executes MT5 orders itself.
 */

import app from "./index.js";
import { AutoTradingControl } from "./auto_trading_control.js";

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
const CONTROL_OBJECT_NAME = "global-demo-auto-trading";
const CONTROL_PATH = "/api/auto-trading";
const UI_SCRIPT = "/auto-trading-control.js";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function unauthorized() {
  return json({ error: "unauthorized" }, 401);
}

function verifyControlToken(request, env) {
  const expected = env.DEMO_CONTROL_TOKEN;
  if (!expected || typeof expected !== "string") {
    return json({ error: "demo control token is not configured" }, 503);
  }
  const actual = request.headers.get("authorization") || "";
  const prefix = "Bearer ";
  if (!actual.startsWith(prefix)) return unauthorized();
  const token = actual.slice(prefix.length);
  if (token.length !== expected.length) return unauthorized();

  let mismatch = 0;
  for (let i = 0; i < expected.length; i += 1) {
    mismatch |= expected.charCodeAt(i) ^ token.charCodeAt(i);
  }
  return mismatch === 0 ? null : unauthorized();
}

function controlStub(env) {
  const id = env.AUTO_TRADING_CONTROL.idFromName(CONTROL_OBJECT_NAME);
  return env.AUTO_TRADING_CONTROL.get(id);
}

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

async function handleControlRequest(request, env) {
  const authError = verifyControlToken(request, env);
  if (authError) return authError;

  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === CONTROL_PATH) {
    return controlStub(env).fetch(new Request("https://control/state", { method: "GET" }));
  }

  if (request.method === "POST" && url.pathname === CONTROL_PATH) {
    return controlStub(env).fetch(new Request("https://control/state", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
    }));
  }

  if (request.method === "POST" && url.pathname === CONTROL_PATH + "/heartbeat") {
    const headers = new Headers();
    const runtimeId = request.headers.get("x-aria-runtime-id");
    if (runtimeId) headers.set("x-aria-runtime-id", runtimeId);
    return controlStub(env).fetch(new Request("https://control/heartbeat", {
      method: "POST",
      headers,
    }));
  }

  return json({ error: "not found" }, 404);
}

async function injectAutoTradingScript(response) {
  if (!response.ok) return response;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("text/html")) return response;
  const content = await response.text();
  if (content.includes(UI_SCRIPT)) return response;
  const injected = content.replace("</body>", `  <script src="${UI_SCRIPT}"></script>\n</body>`);
  if (injected === content) return response;

  const headers = new Headers(response.headers);
  headers.delete("content-length");
  headers.delete("content-encoding");
  headers.set("cache-control", "no-store");
  return new Response(injected, { status: response.status, headers });
}

export { AutoTradingControl };

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === CONTROL_PATH || url.pathname === CONTROL_PATH + "/heartbeat") {
      return handleControlRequest(request, env);
    }

    const ttl = FRESH_TTL_MS[url.pathname];
    const staleTtl = STALE_TTL_MS[url.pathname];

    if (!ttl || request.method !== "GET") {
      return injectAutoTradingScript(await app.fetch(request, env, ctx));
    }

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
