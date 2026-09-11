import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { Mt5MarketStore } from "../worker/mt5_market.js";
import { handleSignalParityV2 } from "../worker/signal_parity_v2.js";

class MemoryStorage {
  constructor() { this.values = new Map(); }
  async get(key) { return this.values.get(key); }
  async put(key, value) { this.values.set(key, value); }
}

function storeContext() {
  return { storage: new MemoryStorage() };
}

test("MT5 bridge payload survives Store -> /api/market -> /api/signal", async () => {
  const payload = JSON.parse(fs.readFileSync(new URL("../.github/e2e_mt5_payload.json", import.meta.url), "utf8"));
  const ctx = storeContext();
  const store = new Mt5MarketStore(ctx, {});

  const ingest = await store.fetch(new Request("https://mt5.internal/ingest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  }));
  assert.equal(ingest.status, 200);

  const marketResponse = await store.fetch(new Request("https://mt5.internal/market?symbol=EUR/USD&timeframe=15m"));
  assert.equal(marketResponse.status, 200);
  const market = await marketResponse.json();
  assert.equal(market.source, "mt5");
  assert.equal(market.execution, "NONE");
  assert.equal(market.candles.length, payload.candles.length);
  assert.equal(market.live_candle.time, payload.live_candle.time);
  assert.notEqual(market.live_candle.time, market.candles.at(-1).time);

  const signalResponse = await handleSignalParityV2(
    new Request("https://example.test/api/signal?symbol=EUR/USD&timeframe=15m"),
    { MT5_MARKET: { idFromName() { return "market"; }, get() { return store; } } },
  );
  assert.equal(signalResponse.status, 200);
  const signal = await signalResponse.json();
  assert.equal(signal.source, "mt5");
  assert.equal(signal.execution, "NONE");
  assert.equal(signal.candles_used, payload.candles.length);
  assert.equal(signal.price, payload.price);
  assert.equal(signal.live_candle.time, payload.live_candle.time);
});

test("MT5 Store rejects a forming candle duplicated in completed candles", async () => {
  const payload = JSON.parse(fs.readFileSync(new URL("../.github/e2e_mt5_payload.json", import.meta.url), "utf8"));
  payload.live_candle = { ...payload.live_candle, time: payload.candles.at(-1).time };
  const store = new Mt5MarketStore(storeContext(), {});
  const response = await store.fetch(new Request("https://mt5.internal/ingest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  }));
  assert.equal(response.status, 400);
  const body = await response.json();
  assert.equal(body.error, "bad_request");
});
