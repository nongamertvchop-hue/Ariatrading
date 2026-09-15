import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { Mt5MarketStore, completedFingerprint } from "../worker/mt5_market.js";
import { handleSignalParityV2 } from "../worker/signal_parity_v2.js";

function storageContext() {
  const data = new Map();
  return {
    ctx: {
      storage: {
        async get(key) { return data.get(key); },
        async put(key, value) { data.set(key, value); },
      },
    },
    data,
  };
}

function ingestRequest(payload) {
  return new Request("https://mt5.internal/ingest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function marketPayload() {
  const now = Math.floor(Date.now() / 1000);
  const base = (Math.floor(now / 900) - 24) * 900;
  const candles = Array.from({ length: 24 }, (_, i) => ({
    time: base + i * 900,
    open: 1.1000 + i * 0.0001,
    high: 1.1005 + i * 0.0001,
    low: 1.0995 + i * 0.0001,
    close: 1.1002 + i * 0.0001,
  }));
  const live = { ...candles.at(-1), time: candles.at(-1).time + 900 };
  return {
    symbol: "EUR/USD",
    timeframe: "15m",
    candles,
    live_candle: live,
    price: live.close,
    received_at: now,
  };
}

test("MT5 market store fingerprints the completed candle snapshot", async () => {
  const { ctx } = storageContext();
  const api = new Mt5MarketStore(ctx, {});
  const response = await api.fetch(ingestRequest(marketPayload()));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.match(body.market_fingerprint, /^[0-9a-f]{64}$/);
  const market = await api.fetch(new Request("https://mt5.internal/market?symbol=EUR/USD&timeframe=15m"));
  assert.equal(market.status, 200);
  const marketBody = await market.json();
  assert.equal(marketBody.market_fingerprint, body.market_fingerprint);
});

test("Python-generated MT5 fixture fingerprint matches the Worker canonical algorithm", async () => {
  const fixturePath = ".github/e2e_mt5_payload.json";
  if (!fs.existsSync(fixturePath)) return;
  const payload = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
  const fingerprint = await completedFingerprint("EUR/USD", "15m", payload.candles);
  assert.equal(fingerprint, payload.market_fingerprint);
});

test("MT5 market store rejects duplicate or out-of-order completed timestamps", async () => {
  const { ctx } = storageContext();
  const api = new Mt5MarketStore(ctx, {});
  const payload = marketPayload();
  const response = await api.fetch(ingestRequest({ ...payload, candles: [payload.candles[1], payload.candles[0]], live_candle: payload.live_candle }));
  assert.equal(response.status, 400);
});

test("signal response is bound to the MT5 market fingerprint", async () => {
  const payload = marketPayload();
  const fingerprint = "b".repeat(64);
  const env = {
    MT5_MARKET: {
      idFromName() { return "market-id"; },
      get() {
        return {
          async fetch() {
            return new Response(JSON.stringify({ ...payload, source: "mt5", market_fingerprint: fingerprint, data_quality: { ok: true, age_seconds: 1 } }), { status: 200 });
          },
        };
      },
    },
  };
  const response = await handleSignalParityV2(new Request("https://example.test/api/signal?symbol=EUR/USD&timeframe=15m"), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.market_fingerprint, fingerprint);
});

test("browser runtime contains a fail-closed chart/strategy fingerprint check", () => {
  const source = fs.readFileSync(new URL("../Webaria/live-market.js", import.meta.url), "utf8");
  assert.match(source, /strategy\.market_fingerprint!==payload\.market_fingerprint/);
  assert.match(source, /refusing mixed-state render/);
  assert.match(source, /preservePrevious/);
});

test("legacy Pages market endpoint requires the fingerprint contract", () => {
  const source = fs.readFileSync(new URL("../Webaria/functions/api/market.js", import.meta.url), "utf8");
  assert.match(source, /market_fingerprint/);
  assert.match(source, /runtime market fingerprint rejected/);
  assert.match(source, /rawTime = raw\?\.datetime \?\? raw\?\.time/);
});
