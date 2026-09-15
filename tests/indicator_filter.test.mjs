import assert from "node:assert/strict";
import test from "node:test";

import { indicatorContext } from "../worker/indicators.js";

function candle(close, previousClose) {
  return {
    open: previousClose,
    high: Math.max(close, previousClose) + 0.0005,
    low: Math.min(close, previousClose) - 0.0005,
    close,
  };
}

test("LONG indicator context remains allowed when directional evidence is supportive", () => {
  const candles = [];
  let previous = 1;
  for (let index = 0; index < 60; index += 1) {
    const close = previous + 0.001;
    candles.push(candle(close, previous));
    previous = close;
  }
  const context = indicatorContext(candles, "LONG");
  assert.ok(context.confirmations >= 2);
  assert.equal(context.allowed, true);
  assert.notEqual(context.confirmation_state, "OPPOSED");
});

test("LONG indicator context vetoes only a full three-signal contradiction", () => {
  const candles = [];
  let previous = 2;
  for (let index = 0; index < 60; index += 1) {
    const close = previous - 0.001;
    candles.push(candle(close, previous));
    previous = close;
  }
  const context = indicatorContext(candles, "LONG");
  assert.equal(context.opposing, 3);
  assert.equal(context.confirmations, 0);
  assert.equal(context.allowed, false);
  assert.equal(context.confirmation_state, "OPPOSED");
});
