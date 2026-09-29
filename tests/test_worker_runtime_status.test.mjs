import test from "node:test";
import assert from "node:assert/strict";
import {
  validateRuntimeStatus,
  assertCompletedChronology,
} from "../worker/mt5_market.js";
import { validatePublicApiRequest } from "../bodyguard/worker/bodyguard.js";

test("accepts a sanitized DEMO runtime status", () => {
  const result = validateRuntimeStatus({
    runtime_state: "RUNNING",
    reason: "cycle complete",
    mode: "DEMO",
    symbols: ["EURUSD"],
    timeframe: "15m",
    processed: 1,
    control_state: "RUN",
    control_generation: 3,
    updated_at: "2026-09-15T03:30:00.000Z",
    account_login: "must-not-pass",
  });
  assert.equal(result.runtime_state, "RUNNING");
  assert.equal(result.mode, "DEMO");
  assert.equal(result.processed, 1);
  assert.equal("account_login" in result, false);
});

test("rejects runtime telemetry that claims LIVE mode", () => {
  assert.throws(
    () => validateRuntimeStatus({ mode: "LIVE", runtime_state: "RUNNING" }),
    /runtime_status must be DEMO/,
  );
});

test("rejects invalid runtime state and negative counters", () => {
  assert.throws(
    () => validateRuntimeStatus({ runtime_state: "BUY_NOW" }),
    /invalid runtime_state/,
  );
  assert.throws(
    () => validateRuntimeStatus({ processed: -1 }),
    /invalid runtime_status processed/,
  );
});

test("allows the read-only MT5 diagnostics API path", () => {
  const request = new Request(
    "https://ariatrading.pages.dev/api/mt5/status?symbol=EUR/USD",
  );
  const decision = validatePublicApiRequest(request);
  assert.equal(decision.ok, true);
});

test("still rejects non-chronological candle data at the market boundary", () => {
  assert.throws(
    () => assertCompletedChronology([
      { time: 100, open: 1, high: 2, low: 0, close: 1 },
      { time: 100, open: 1, high: 2, low: 0, close: 1 },
    ]),
    /strictly chronological/,
  );
});
