import assert from "node:assert/strict";
import test from "node:test";
import { indicatorContext } from "../worker/indicators.js";

function makeCandles(start, delta, count = 60) {
  const candles = [];
  let previous = start;
  for (let index = 0; index < count; index += 1) {
    const close = previous + delta;
    candles.push({ open: previous, high: Math.max(previous, close) + 0.0005, low: Math.min(previous, close) - 0.0005, close });
    previous = close;
  }
  return candles;
}

test("LONG indicator context remains supportive when directional evidence agrees", () => {
  const context = indicatorContext(makeCandles(1, 0.001), "LONG");
  assert.ok(context.confirmations >= 2);
  assert.equal(context.confirmation_state, "SUPPORTIVE");
});

test("LONG indicator context identifies a full three-signal contradiction", () => {
  const context = indicatorContext(makeCandles(2, -0.001), "LONG");
  assert.equal(context.confirmations, 0);
  assert.equal(context.confirmation_state, "OPPOSED");
  assert.notEqual(context.trend, "UNAVAILABLE");
  assert.notEqual(context.momentum, "UNAVAILABLE");
  assert.notEqual(context.macd_momentum, "UNAVAILABLE");
});
