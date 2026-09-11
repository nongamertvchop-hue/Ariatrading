import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { validateRealtimeFeed, resetRealtimeFeedGuard } from "../worker/realtime_feed_guard.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, "..");
const ENTRY = path.join(ROOT, "worker", "entry.js");

test("Worker strategy route imports and invokes the canonical realtime feed guard for MT5", () => {
  const source = fs.readFileSync(ENTRY, "utf8");
  assert.match(source, /import \{ validateRealtimeFeed, acceptRealtimeFeed \} from "\.\/realtime_feed_guard\.js";/);
  assert.match(source, /const source=body\?\.source==="mt5"\?"mt5":"simulation";/);
  assert.match(source, /if\(source==="mt5"\)\{/);
  assert.match(source, /const quality=validateRealtimeFeed\(body\.candles,timeframe,symbol\);/);
  assert.match(source, /if\(source==="mt5"\) acceptRealtimeFeed\(body\.candles,timeframe,symbol\);/);
});

test("MT5 epoch strategy input cannot bypass duplicate or chronological feed checks", () => {
  resetRealtimeFeedGuard();
  const candles = [
    { open: 1, high: 1.01, low: 0.99, close: 1, time: 1788894000 },
    { open: 1, high: 1.01, low: 0.99, close: 1, time: 1788894900 },
  ];
  const fresh = validateRealtimeFeed(candles, "15m", "EUR/USD", new Date(1788894960 * 1000));
  assert.equal(fresh.ok, true);

  const duplicate = validateRealtimeFeed([candles[0], candles[0]], "15m", "EUR/USD", new Date(1788894960 * 1000));
  assert.equal(duplicate.reason, "duplicate bar timestamps");

  const outOfOrder = validateRealtimeFeed([candles[1], candles[0]], "15m", "EUR/USD", new Date(1788894960 * 1000));
  assert.equal(outOfOrder.reason, "bars must be strictly chronological");
  resetRealtimeFeedGuard();
});
