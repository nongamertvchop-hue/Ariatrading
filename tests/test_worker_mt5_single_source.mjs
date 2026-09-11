import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { handleSignalParityV2 } from "../worker/signal_parity_v2.js";

function mockEnv(payload) {
  return {
    MT5_MARKET: {
      idFromName() { return "market-id"; },
      get() {
        return {
          async fetch() {
            return new Response(JSON.stringify(payload), {
              status: 200,
              headers: { "content-type": "application/json" },
            });
          },
        };
      },
    },
  };
}

test("/api/signal reads candles from the MT5 market binding", async () => {
  const candles = Array.from({ length: 12 }, (_, i) => ({
    time: 1_700_000_000 + i * 900,
    open: 1.1000 + i * 0.0001,
    high: 1.1005 + i * 0.0001,
    low: 1.0995 + i * 0.0001,
    close: 1.1002 + i * 0.0001,
  }));
  const response = await handleSignalParityV2(
    new Request("https://example.test/api/signal?symbol=EUR/USD&timeframe=15m"),
    mockEnv({
      source: "mt5",
      symbol: "EUR/USD",
      timeframe: "15m",
      candles,
      live_candle: candles.at(-1),
      price: candles.at(-1).close,
      data_quality: { ok: true, age_seconds: 1 },
    }),
  );
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.source, "mt5");
  assert.equal(body.candles_used, candles.length);
  assert.equal(body.price, candles.at(-1).close);
});

test("/api/signal fails closed when MT5 data is unavailable", async () => {
  const response = await handleSignalParityV2(
    new Request("https://example.test/api/signal?symbol=EUR/USD&timeframe=15m"),
    {
      MT5_MARKET: {
        idFromName() { return "market-id"; },
        get() {
          return { async fetch() { return new Response(JSON.stringify({ error: "mt5_feed_unavailable" }), { status: 503 }); } };
        },
      },
    },
  );
  assert.equal(response.status, 503);
});

test("Worker entry does not route /api/signal to the legacy synthetic fallback", () => {
  const source = fs.readFileSync(new URL("../worker/entry.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /if\(!env\.TWELVE_DATA_API_KEY\)\{if\(pathname===\"\/api\/signal\"\)/);
  assert.match(source, /if\(!env\.TWELVE_DATA_API_KEY\)\{if\(pathname===\"\/api\/price\"\)/);
});
