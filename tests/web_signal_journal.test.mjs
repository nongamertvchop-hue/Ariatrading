import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(HERE, "..", "Webaria", "signal-journal.js"), "utf8");
const context = { globalThis: {} };
context.window = context.globalThis;
vm.runInNewContext(source, context);
const journal = context.globalThis.WebariaSignalJournal;

 test("journal dedup uses event_id instead of polling timestamp", () => {
  const existing = [{
    event_id: "sig_abc",
    at: "2026-09-09T01:00:00Z",
    tf: "15m",
    signal: "WAIT",
    structure: "RANGE",
    score: null,
  }];

  const result = journal.appendUnique(existing, [{
    event_id: "sig_abc",
    at: "2026-09-09T01:01:00Z",
    tf: "15m",
    signal: "WAIT",
    structure: "RANGE",
    score: null,
  }], 100);

  assert.equal(result.length, 1);
  assert.equal(result[0].event_id, "sig_abc");
});

test("journal keeps distinct event ids and enforces the bounded retention", () => {
  const existing = [];
  const incoming = Array.from({ length: 105 }, (_, i) => ({
    event_id: `sig_${i}`,
    at: `2026-09-09T00:${String(i).padStart(2, "0")}:00Z`,
    tf: "15m",
    signal: i % 2 ? "LONG" : "WAIT",
    structure: "RANGE",
    score: i,
  }));

  const result = journal.appendUnique(existing, incoming, 100);
  assert.equal(result.length, 100);
  assert.equal(result[0].event_id, "sig_5");
  assert.equal(result.at(-1).event_id, "sig_104");
});

test("legacy entries get a deterministic fallback identity", () => {
  const a = journal.entryKey({ tf: "15m", bar_time: "2026-09-09T01:15:00Z", signal: "WAIT", structure: "RANGE", score: null });
  const b = journal.entryKey({ tf: "15m", bar_time: "2026-09-09T01:15:00Z", signal: "WAIT", structure: "RANGE", score: null, at: "different" });
  assert.equal(a, b);
});
