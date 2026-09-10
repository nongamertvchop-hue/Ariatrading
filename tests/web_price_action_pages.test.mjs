import test from "node:test";
import assert from "node:assert/strict";
import { evaluatePriceAction } from "../Webaria/functions/api/signal.js";

function candle(open, high, low, close) {
  return { open, high, low, close, datetime: "2026-01-01T00:00:00.000Z" };
}

test("Pages price-action evaluator requires completed-candle history", () => {
  const candles = Array.from({ length: 20 }, (_, i) => candle(1 + i * 0.001, 1.002 + i * 0.001, 0.998 + i * 0.001, 1.001 + i * 0.001));
  const result = evaluatePriceAction(candles, "15m");
  assert.equal(result.signal, "WAIT");
  assert.equal(result.strategy_version, "wiki-price-action-v1");
});

test("Pages price-action evaluator rejects unsupported timeframes", () => {
  assert.throws(() => evaluatePriceAction([], "2m"), /unsupported timeframe/);
});

test("Pages evaluator returns a stable WAIT contract for flat OHLC data", () => {
  const candles = Array.from({ length: 30 }, () => candle(1, 1, 1, 1));
  const result = evaluatePriceAction(candles, "15m");
  assert.equal(result.signal, "WAIT");
  assert.equal(result.structure_bias, "UNKNOWN");
  assert.equal(result.breakout_state, "NO_BREAKOUT");
  assert.equal(result.entry_reference, null);
  assert.equal(result.stop_reference, null);
});
