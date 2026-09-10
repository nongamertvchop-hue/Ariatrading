import assert from "node:assert/strict";
import test from "node:test";

import {
  detectProbe,
  detectPrototypePollution,
  getCorsHeaders,
  publicError,
  validatePublicApiRequest,
} from "../bodyguard/worker/bodyguard.js";
import { sanitizeForBoundary, REDACTED } from "../bodyguard/worker/redaction.js";

const makeRequest = (url, options = {}) =>
  new Request(url, options);

test("allows the supported market API route", () => {
  const request = makeRequest("https://ariatrading.pages.dev/api/market?symbol=EUR/USD&timeframe=15m");
  assert.equal(validatePublicApiRequest(request).ok, true);
});

test("blocks broker execution paths", () => {
  for (const path of ["/api/order", "/api/execute", "/api/trade", "/api/buy", "/api/sell", "/api/mt5"]) {
    const request = makeRequest(`https://ariatrading.pages.dev${path}`);
    const decision = validatePublicApiRequest(request);
    assert.equal(decision.ok, false);
    assert.equal(decision.reason, "execution_surface_forbidden");
  }
});

test("blocks traversal and encoded probes", () => {
  const direct = makeRequest("https://ariatrading.pages.dev/api/price?path=../etc/passwd");
  assert.equal(detectProbe(direct).ok, false);

  const encoded = makeRequest("https://ariatrading.pages.dev/api/price?path=%252e%252e%252fetc%252fpasswd");
  assert.equal(detectProbe(encoded).ok, false);
});

test("blocks prototype-pollution keys at every nested level", () => {
  assert.equal(detectPrototypePollution({ safe: { nested: { __proto__: "x" } } }).ok, true);
  assert.equal(detectPrototypePollution({ safe: { nested: { constructor: { prototype: {} } } } }).ok, false);
});

test("rejects unsupported methods and oversized queries", () => {
  const method = makeRequest("https://ariatrading.pages.dev/api/price", { method: "POST" });
  assert.equal(validatePublicApiRequest(method).reason, "method_not_allowed");

  const longQuery = makeRequest(`https://ariatrading.pages.dev/api/price?x=${"a".repeat(600)}`);
  assert.equal(validatePublicApiRequest(longQuery).reason, "query_too_long");
});

test("allows only configured CORS origins", () => {
  const allowed = makeRequest("https://ariatrading.pages.dev/api/price", {
    headers: { Origin: "https://webaria.pages.dev" },
  });
  assert.equal(getCorsHeaders(allowed)["access-control-allow-origin"], "https://webaria.pages.dev");

  const denied = makeRequest("https://ariatrading.pages.dev/api/price", {
    headers: { Origin: "https://evil.example" },
  });
  assert.equal(getCorsHeaders(denied)["access-control-allow-origin"], undefined);
});

test("public errors do not reflect attacker-controlled messages", async () => {
  const response = publicError(400, "invalid_symbol", "SECRET_INTERNAL_STACK_TRACE");
  const body = await response.json();
  assert.equal(body.message, "invalid symbol");
  assert.equal(JSON.stringify(body).includes("SECRET_INTERNAL_STACK_TRACE"), false);
});

test("redacts sensitive keys and common secret shapes", () => {
  const result = sanitizeForBoundary({
    api_key: "real-secret",
    nested: { password: "hunter2" },
    bearer: "Bearer abcdefghijklmnop",
    token: "eyJaaaaaaaaaaa.bbbbbbbbbbb.ccccccccccc",
    safe: "hello",
  });
  assert.equal(result.api_key, REDACTED);
  assert.equal(result.nested.password, REDACTED);
  assert.equal(result.bearer, REDACTED);
  assert.equal(result.token, REDACTED);
  assert.equal(result.safe, "hello");
});

test("redaction bounds deeply nested payloads", () => {
  const deep = { a: { b: { c: { d: { e: { f: "secret" } } } } } };
  const result = sanitizeForBoundary(deep, { maxDepth: 3 });
  assert.equal(result.a.b.c, REDACTED);
});
