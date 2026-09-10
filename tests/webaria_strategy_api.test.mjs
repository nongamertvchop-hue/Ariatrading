import test from "node:test";
import assert from "node:assert/strict";
import { onRequestPost } from "../Webaria/functions/api/strategy.js";

function candles(count = 30) {
  return Array.from({ length: count }, (_, i) => {
    const open = 1.1 + i * 0.0001;
    const close = open + (i % 2 ? 0.00005 : -0.00002);
    return {
      datetime: new Date(Date.UTC(2026, 0, 1, 0, i)).toISOString(),
      open,
      high: Math.max(open, close) + 0.0002,
      low: Math.min(open, close) - 0.0002,
      close,
    };
  });
}

async function call(body) {
  return onRequestPost({ request: new Request("https://example.test/api/strategy", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }) });
}

test("strategy adapter evaluates candles supplied by the MT5 market bridge", async () => {
  const response = await call({ symbol: "EUR/USD", timeframe: "15m", candles: candles() });
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.source, "mt5");
  assert.equal(payload.execution, "NONE");
  assert.equal(payload.candles_used, 30);
  assert.ok(["LONG", "SHORT", "WAIT"].includes(payload.signal));
});

test("strategy adapter rejects insufficient candle history", async () => {
  const response = await call({ symbol: "EUR/USD", timeframe: "15m", candles: candles(19) });
  assert.equal(response.status, 400);
});

test("strategy adapter rejects malformed OHLC", async () => {
  const rows = candles();
  rows[0].high = rows[0].low - 1;
  const response = await call({ symbol: "EUR/USD", timeframe: "15m", candles: rows });
  assert.equal(response.status, 400);
});
