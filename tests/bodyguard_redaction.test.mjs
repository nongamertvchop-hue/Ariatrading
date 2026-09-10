import test from "node:test";
import assert from "node:assert/strict";
import { REDACTED, sanitizeForBoundary } from "../bodyguard/worker/redaction.js";

test("redacts sensitive keys recursively", () => {
  const result = sanitizeForBoundary({
    symbol: "EUR/USD",
    credentials: { api_key: "secret", password: "hunter2" },
    nested: [{ authorization: "Bearer " + "abcdefghijklmnop" }],
  });
  assert.equal(result.symbol, "EUR/USD");
  assert.equal(result.credentials.api_key, REDACTED);
  assert.equal(result.credentials.password, REDACTED);
  assert.equal(result.nested[0].authorization, REDACTED);
});

test("redacts secret-shaped values without relying on key names", () => {
  const result = sanitizeForBoundary({
    message: "Bearer " + "abcdefghijklmnop",
    token: "eyJ" + "aaaaaaaaaaaa.bbbbbbbbbbbb.cccccccccccc",
    github: "ghp_" + "abcdefghijklmnopqrstuvwxyz123456",
  });
  assert.equal(result.message, REDACTED);
  assert.equal(result.token, REDACTED);
  assert.equal(result.github, REDACTED);
});

test("bounds nested and wide payloads", () => {
  const deep = { a: { b: { c: { d: { e: "value" } } } } };
  const wide = Object.fromEntries(Array.from({ length: 250 }, (_, i) => [String(i), i]));
  assert.equal(sanitizeForBoundary(deep, { maxDepth: 3 }).a.b.c, REDACTED);
  const result = sanitizeForBoundary(wide, { maxItems: 10 });
  assert.equal(Object.keys(result).length, 11);
  assert.equal(result["[TRUNCATED]"], REDACTED);
});
