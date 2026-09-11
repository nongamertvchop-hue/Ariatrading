import assert from "node:assert/strict";
import test from "node:test";
import { Mt5MarketStore } from "../worker/mt5_market.js";

function store() {
  const data = new Map();
  return new Mt5MarketStore({
    storage: {
      async get(key) { return data.get(key); },
      async put(key, value) { data.set(key, value); },
    },
  }, {});
}

const now = Math.floor(Date.now() / 1000);
const completed = [
  { time: now - 120, open: 1.1000, high: 1.1010, low: 1.0990, close: 1.1005 },
  { time: now - 60, open: 1.1005, high: 1.1020, low: 1.1000, close: 1.1015 },
];
const live = { time: now, open: 1.1015, high: 1.1025, low: 1.1010, close: 1.1020 };

function request(payload) {
  return new Request("https://mt5.internal/ingest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

test("accepts completed candles separately from the forming candle", async () => {
  const api = store();
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: completed, live_candle: live, price: live.close, received_at: now }));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.match(body.market_fingerprint, /^[0-9a-f]{64}$/);
  const stored = await api.state.storage.get("EUR/USD:1m");
  assert.equal(stored.candles.at(-1).time, now - 60);
  assert.equal(stored.live_candle.time, now);
  assert.equal(stored.market_fingerprint, body.market_fingerprint);
});

test("serves the same completed-candle fingerprint from the GET path", async () => {
  const api = store();
  await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: completed, live_candle: live, price: live.close, received_at: now }));
  const response = await api.fetch(new Request("https://mt5.internal/market?symbol=EUR/USD&timeframe=1m"));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.match(body.market_fingerprint, /^[0-9a-f]{64}$/);
  assert.equal(body.market_fingerprint, (await api.state.storage.get("EUR/USD:1m")).market_fingerprint);
});

test("rejects non-chronological completed candles", async () => {
  const api = store();
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: [completed[1], completed[0]], live_candle: live, price: live.close, received_at: now }));
  assert.equal(response.status, 400);
});

test("rejects a live candle duplicated inside completed history", async () => {
  const api = store();
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: [...completed, live], live_candle: live, price: live.close, received_at: now }));
  assert.equal(response.status, 400);
});

test("rejects a forming candle that is not newer than completed history", async () => {
  const api = store();
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: completed, live_candle: completed.at(-1), price: completed.at(-1).close, received_at: now }));
  assert.equal(response.status, 400);
});

test("rejects stale broker payloads", async () => {
  const api = store();
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: completed, live_candle: live, price: live.close, received_at: now - 91 }));
  assert.equal(response.status, 400);
});

test("rejects malformed OHLC relationships", async () => {
  const api = store();
  const bad = { ...live, high: 1.1000 };
  const response = await api.fetch(request({ symbol: "EUR/USD", timeframe: "1m", candles: completed, live_candle: bad, price: bad.close, received_at: now }));
  assert.equal(response.status, 400);
});
