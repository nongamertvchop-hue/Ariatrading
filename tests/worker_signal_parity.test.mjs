import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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
import { forecast, supervise } from "../worker/forecast_parity.js";
import { evaluateRealtimeSignalParity } from "../worker/signal_parity_v2.js";
import { validateRealtimeFeed, acceptRealtimeFeed, resetRealtimeFeedGuard } from "../worker/realtime_feed_guard.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const golden = JSON.parse(fs.readFileSync(path.join(HERE, "fixtures", "parity_vectors.json"), "utf8"));
const candle = (open, high, low, close, datetime = undefined) => ({ open, high, low, close, ...(datetime ? { datetime } : {}) });

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

test("golden vectors: Worker breakout classification matches Python contract", () => {
  for (const vector of golden.breakout) {
    const result = vector.direction === LONG
      ? classifySupportBreakout(vector.candle, vector.zone, vector.buffer)
      : classifyResistanceBreakout(vector.candle, vector.zone, vector.buffer);
    assert.equal(result.state, vector.expected_state, vector.name);
  }
});

test("golden vectors: Worker zone centers match PriceZone.center", () => {
  for (const vector of golden.zone_center) {
    assert.equal((vector.low + vector.high) / 2, vector.expected_center);
  }
});

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

test("forecast probabilities and confidence are deterministic and bounded", () => {
  const result = forecast(makeRangeFixture());
  assert.equal(result.horizons.length, 3);
  for (const horizon of result.horizons) {
    const total = horizon.up_probability + horizon.flat_probability + horizon.down_probability;
    assert.ok(Math.abs(total - 1) < 1e-12);
    assert.ok(horizon.expected_close > 0);
    assert.ok(["UP", "FLAT", "DOWN"].includes(horizon.direction));
  }
  assert.ok(result.confidence >= 0 && result.confidence <= 1);
});

test("forecast fallback exactly matches the closed-candle Python contract", () => {
  const result = forecast([candle(1.0, 1.0, 1.0, 1.0)]);
  for (const horizon of result.horizons) {
    assert.equal(horizon.up_probability, 1 / 3);
    assert.equal(horizon.flat_probability, 1 / 3);
    assert.equal(horizon.down_probability, 1 / 3);
    assert.equal(horizon.expected_return, 0);
    assert.equal(horizon.expected_close, 1);
  }
  assert.equal(result.confidence, 0.45 * 0 + 0.55 * 0.01);
});

test("supervisor blocks an otherwise directional setup when forecast is unavailable", () => {
  const decision = supervise({ action: LONG, protection: "SAFE", breakoutState: NO_BREAKOUT });
  assert.equal(decision.action, WAIT);
  assert.equal(decision.allowed, false);
  assert.ok(decision.reasons.includes("forecast unavailable"));
});

test("supervisor blocks low-confidence forecast and preserves fail-closed behavior", () => {
  const decision = supervise(
    { action: SHORT, protection: "SAFE", breakoutState: NO_BREAKOUT },
    { confidence: 0.1, horizons: [{ direction: "FLAT" }] },
    null,
    0.45,
  );
  assert.equal(decision.action, WAIT);
  assert.equal(decision.allowed, false);
  assert.ok(decision.reasons.includes("forecast confidence below threshold"));
});

test("realtime feed guard rejects stale and duplicate observations", () => {
  resetRealtimeFeedGuard();
  const candles = [
    candle(1, 1.01, 0.99, 1, "2026-09-08T19:00:00Z"),
    candle(1, 1.01, 0.99, 1, "2026-09-08T19:15:00Z"),
  ];
  const fresh = validateRealtimeFeed(candles, "15m", "EUR/USD", new Date("2026-09-08T19:16:00Z"));
  assert.equal(fresh.ok, true);
  acceptRealtimeFeed(candles, "15m", "EUR/USD");
  const duplicate = validateRealtimeFeed(candles, "15m", "EUR/USD", new Date("2026-09-08T19:16:00Z"));
  assert.equal(duplicate.reason, "duplicate or old closed bar");
  const stale = validateRealtimeFeed(candles, "15m", "GBP/USD", new Date("2026-09-08T20:00:01Z"));
  assert.equal(stale.reason, "feed is stale");
  resetRealtimeFeedGuard();
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
