import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

import { evaluateRealtimeSignalParity } from "../worker/signal_parity_v2.js";
import { resetRealtimeFeedGuard } from "../worker/realtime_feed_guard.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, "..");
const cases = JSON.parse(fs.readFileSync(path.join(HERE, "fixtures", "realtime_parity_cases.json"), "utf8")).cases;

function runPythonOracle() {
  const env = { ...process.env, PYTHONPATH: [ROOT, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  return JSON.parse(execFileSync("python", [path.join(HERE, "realtime_parity_oracle.py")], {
    cwd: ROOT,
    env,
    input: JSON.stringify({ cases }),
    encoding: "utf8",
  }));
}

function compactZone(zone) {
  if (!zone) return null;
  return { kind: zone.kind, low: zone.low, high: zone.high, touches: zone.touches, center: zone.center };
}

function compactIndicators(values) {
  if (!values) return null;
  return { ema20: values.ema20, ema50: values.ema50, ema200: values.ema200, rsi14: values.rsi14, atr14: values.atr14, adx14: values.adx14, macd: values.macd, macd_signal: values.macd_signal, macd_histogram: values.macd_histogram };
}

function compact(result) {
  return {
    signal: result.signal,
    state: result.state,
    reason: result.reason,
    price: result.price,
    bar_time: result.bar_time,
    structure_bias: result.structure_bias,
    zone: compactZone(result.zone),
    entry_reference: result.entry_reference,
    stop_reference: result.stop_reference,
    breakout_state: result.breakout_state,
    protection: result.protection,
    score: result.score == null ? null : { total: result.score.total },
    indicators: compactIndicators(result.indicators),
    indicator_context: result.indicator_context ? {
      values: compactIndicators(result.indicator_context.values),
      trend: result.indicator_context.trend,
      momentum: result.indicator_context.momentum,
      macd_momentum: result.indicator_context.macd_momentum,
      trend_strength: result.indicator_context.trend_strength,
      direction: result.indicator_context.direction,
      confirmations: result.indicator_context.confirmations,
      confirmation_state: result.indicator_context.confirmation_state,
    } : null,
    support: compactZone(result.support),
    resistance: compactZone(result.resistance),
    forecast: {
      confidence: result.forecast?.confidence ?? null,
      horizons: (result.forecast?.horizons ?? []).map((horizon) => ({ direction: horizon.direction, up_probability: horizon.up_probability, flat_probability: horizon.flat_probability, down_probability: horizon.down_probability, expected_return: horizon.expected_return, expected_close: horizon.expected_close })),
    },
    supervisor: result.supervisor ? { action: result.supervisor.action, allowed: result.supervisor.allowed, reasons: [...result.supervisor.reasons] } : null,
  };
}

test("Python realtime monitor and Worker realtime evaluator stay contract-parity aligned", () => {
  const oracle = runPythonOracle();
  assert.equal(oracle.length, cases.length);
  for (const [index, fixture] of cases.entries()) {
    resetRealtimeFeedGuard();
    const result = evaluateRealtimeSignalParity(fixture.candles, fixture.timeframe);
    const expected = oracle[index];
    const { name: _name, ...expectedPayload } = expected;
    assert.deepEqual(compact(result), expectedPayload, fixture.name);
  }
  resetRealtimeFeedGuard();
});
