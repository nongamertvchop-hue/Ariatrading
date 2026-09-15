import assert from "node:assert/strict";
import test from "node:test";

import { adxSeries, atrSeries, calculateIndicators, emaSeries, macdSeries, rsiSeries } from "../worker/indicators.js";

function candlesFromCloses(closes) {
  return closes.map((close) => ({ open: close - 0.1, high: close + 0.2, low: close - 0.2, close }));
}

test("worker indicators have deterministic warmups", () => {
  const candles = candlesFromCloses(Array.from({ length: 220 }, (_, index) => index + 1));
  const snapshot = calculateIndicators(candles);
  assert.notEqual(snapshot.ema20, null);
  assert.notEqual(snapshot.ema50, null);
  assert.notEqual(snapshot.ema200, null);
  assert.notEqual(snapshot.rsi14, null);
  assert.notEqual(snapshot.atr14, null);
  assert.notEqual(snapshot.adx14, null);
  assert.notEqual(snapshot.macd, null);
  assert.notEqual(snapshot.macd_signal, null);
  assert.notEqual(snapshot.macd_histogram, null);
  assert.deepEqual(snapshot, calculateIndicators(candles));
});

test("worker indicator series remain causal", () => {
  const prefix = candlesFromCloses([1, 2, 3, 4, 5]);
  const extended = [...prefix, ...candlesFromCloses([100])];
  assert.equal(emaSeries(prefix, 3)[2], emaSeries(extended, 3)[2]);
  assert.equal(rsiSeries(prefix, 3)[3], rsiSeries(extended, 3)[3]);
});

test("worker indicators expose explicit warmup state", () => {
  const candles = candlesFromCloses(Array.from({ length: 30 }, (_, index) => index + 1));
  assert.equal(emaSeries(candles.slice(0, 19), 20).at(-1), null);
  assert.equal(atrSeries(candles.slice(0, 13), 14).at(-1), null);
  assert.equal(adxSeries(candles.slice(0, 27), 14).at(-1) !== null, true);
  assert.equal(macdSeries(candles.slice(0, 30)).signal.at(-1), null);
});
