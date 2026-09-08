import assert from "node:assert/strict";
import test from "node:test";

import {
  BEARISH,
  FAKE_BREAKOUT,
  LONG,
  NO_BREAKOUT,
  SUPPORT,
  RESISTANCE,
  SHORT,
  TRUE_BREAKOUT,
  WAIT,
  adaptiveZoneTolerance,
  analyzeMarketStructure,
  candlePressure,
  classifyResistanceBreakout,
  classifySupportBreakout,
  findResistanceZones,
  findSupportZones,
  scoreSetup,
} from "../worker/signal_parity.js";
import { evaluateRealtimeSignalParity } from "../worker/signal_parity_v2.js";

const candle = (open, high, low, close) => ({ open, high, low, close });

function makeRangeFixture() {
  return [
    candle(1.1000, 1.1010, 1.0995, 1.1005),
    candle(1.1005, 1.1015, 1.1000, 1.1010),
    candle(1.1010, 1.1020, 1.1002, 1.1014),
    candle(1.1014, 1.1020, 1.0990, 1.0995),
    candle(1.0995, 1.1005, 1.0985, 1.0990),
    candle(1.0990, 1.1010, 1.0980, 1.1007),
    candle(1.1007, 1.1022, 1.1000, 1.1018),
    candle(1.1018, 1.1030, 1.1008, 1.1026),
    candle(1.1026, 1.1032, 1.1005, 1.1010),
    candle(1.1010, 1.1015, 1.0990, 1.1000),
  ];
}

test("support fake breakout matches Python contract", () => {
  const zone = { low: 1.0000, high: 1.0100, center: 1.0050, kind: SUPPORT, touches: 2 };
  const result = classifySupportBreakout(candle(1.0040, 1.0060, 0.9995, 1.0045), zone, 0.0020);
  assert.equal(result.state, FAKE_BREAKOUT);
});

test("support decisive close matches Python true-break contract", () => {
  const zone = { low: 1.0000, high: 1.0100, center: 1.0050, kind: SUPPORT, touches: 2 };
  const result = classifySupportBreakout(candle(1.0020, 1.0030, 0.9970, 0.9979), zone, 0.0020);
  assert.equal(result.state, TRUE_BREAKOUT);
});

test("resistance fake breakout is mirrored correctly", () => {
  const zone = { low: 1.0000, high: 1.0100, center: 1.0050, kind: RESISTANCE, touches: 2 };
  const result = classifyResistanceBreakout(candle(1.0060, 1.0105, 1.0045, 1.0065), zone, 0.0020);
  assert.equal(result.state, FAKE_BREAKOUT);
});

test("resistance decisive close matches Python true-break contract", () => {
  const zone = { low: 1.0000, high: 1.0100, center: 1.0050, kind: RESISTANCE, touches: 2 };
  const result = classifyResistanceBreakout(candle(1.0120, 1.0135, 1.0110, 1.0121), zone, 0.0020);
  assert.equal(result.state, TRUE_BREAKOUT);
});

test("Worker zone centers include the tolerance exactly like PriceZone.center", () => {
  const candles = [
    candle(1.10, 1.11, 1.09, 1.10),
    candle(1.10, 1.105, 1.08, 1.09),
    candle(1.09, 1.095, 1.085, 1.09),
    candle(1.09, 1.11, 1.09, 1.10),
    candle(1.10, 1.105, 1.08, 1.09),
    candle(1.09, 1.095, 1.085, 1.09),
    candle(1.09, 1.10, 1.088, 1.095),
  ];
  const tolerance = adaptiveZoneTolerance(candles, "15m");
  const zones = findSupportZones(candles, tolerance);
  for (const zone of zones) assert.equal(zone.center, (zone.low + zone.high) / 2);
});

test("realtime evaluator returns WAIT instead of error when no zones exist", () => {
  const result = evaluateRealtimeSignalParity(makeRangeFixture(), "15m");
  assert.equal(result.signal, WAIT);
});

test("structure and score enums remain compatible with Python contract", () => {
  const structure = analyzeMarketStructure(makeRangeFixture());
  assert.ok(["BULLISH", BEARISH, "RANGE", "UNKNOWN"].includes(structure.bias));
  const score = scoreSetup(LONG, 2, structure.bias, NO_BREAKOUT, 20);
  assert.equal(score.confirmation, 20);
  assert.equal(score.mtf, 0);
  assert.ok(score.total >= 0 && score.total <= 100);
  assert.equal(candlePressure(candle(1, 1.01, 0.99, 1.009)), "BUYING");
});
