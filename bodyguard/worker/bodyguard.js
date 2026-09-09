/**
 * Bodyguard(Aria) v0.00.0 — Worker-side defensive primitives.
 *
 * Monitor-friendly helpers for request validation, redaction, and
 * lightweight rate signaling. Wire into entry.js in a later version.
 */

export const BODYGUARD_VERSION = "0.00.0";

const DEFAULTS = Object.freeze({
  allowedMethods: ["GET", "HEAD", "OPTIONS"],
  maxQueryLength: 512,
  symbolPattern: /^[A-Z]{3}\/[A-Z]{3}$/,
  allowedTimeframes: new Set(["1m", "5m", "15m", "30m", "1h", "4h", "1D"]),
  rateWindowMs: 60_000,
  rateMax: 60,
});

const rateBuckets = new Map();

function clientKey(request) {
  return (
    request.headers.get("cf-connecting-ip") ||
    request.headers.get("x-forwarded-for") ||
    "unknown"
  );
}

export function securityEvent(level, reason, extra = {}) {
  const row = {
    guard: "Bodyguard(Aria)",
    version: BODYGUARD_VERSION,
    level,
    reason,
    at: new Date().toISOString(),
    ...extra,
  };
  // Avoid logging raw secrets; callers must pass already-safe fields.
  console.log(JSON.stringify(row));
  return row;
}

export function validatePublicApiRequest(request, url = new URL(request.url)) {
  const method = request.method.toUpperCase();
  if (!DEFAULTS.allowedMethods.includes(method)) {
    return { ok: false, status: 405, reason: "method_not_allowed" };
  }
  if (url.search.length > DEFAULTS.maxQueryLength) {
    return { ok: false, status: 414, reason: "query_too_long" };
  }

  if (url.pathname.startsWith("/api/")) {
    const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
    if (!DEFAULTS.symbolPattern.test(symbol)) {
      return { ok: false, status: 400, reason: "invalid_symbol" };
    }
    const timeframe = url.searchParams.get("timeframe");
    if (timeframe && !DEFAULTS.allowedTimeframes.has(timeframe)) {
      return { ok: false, status: 400, reason: "invalid_timeframe" };
    }
  }

  return { ok: true, status: 200, reason: "ok" };
}

export function checkRateLimit(request, opts = {}) {
  const windowMs = opts.windowMs ?? DEFAULTS.rateWindowMs;
  const max = opts.max ?? DEFAULTS.rateMax;
  const key = `${clientKey(request)}:${new URL(request.url).pathname}`;
  const now = Date.now();
  let bucket = rateBuckets.get(key);
  if (!bucket || now - bucket.start > windowMs) {
    bucket = { start: now, count: 0 };
    rateBuckets.set(key, bucket);
  }
  bucket.count += 1;
  if (bucket.count > max) {
    securityEvent("block", "rate_limited", { key, count: bucket.count });
    return { ok: false, status: 429, reason: "rate_limited" };
  }
  return { ok: true, status: 200, reason: "ok", remaining: Math.max(0, max - bucket.count) };
}

export function publicError(status, reason, message) {
  return new Response(
    JSON.stringify({ error: reason, message: String(message || reason).slice(0, 240) }),
    {
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        "x-bodyguard": BODYGUARD_VERSION,
      },
    },
  );
}

export function guardPublicRequest(request) {
  const url = new URL(request.url);
  const basic = validatePublicApiRequest(request, url);
  if (!basic.ok) {
    securityEvent("block", basic.reason, { path: url.pathname });
    return publicError(basic.status, basic.reason, basic.reason);
  }
  if (url.pathname.startsWith("/api/")) {
    const rate = checkRateLimit(request);
    if (!rate.ok) return publicError(rate.status, rate.reason, "too many requests");
  }
  return null; // null => allow through
}
