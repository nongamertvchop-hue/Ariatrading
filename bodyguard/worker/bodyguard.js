/**
 * Bodyguard(Aria) v0.02.0 — Worker enforcement primitives.
 * Defensive only: validate, rate-limit, probe-detect, soft-ban, redact.
 */

export const BODYGUARD_VERSION = "0.02.0";

const DEFAULTS = Object.freeze({
  allowedMethods: ["GET", "HEAD", "OPTIONS"],
  maxQueryLength: 512,
  symbolPattern: /^[A-Z]{3}\/[A-Z]{3}$/,
  allowedTimeframes: new Set(["1m", "5m", "15m", "30m", "1h", "4h", "1D"]),
  allowedApiPaths: new Set(["/api/signal", "/api/price", "/api/live-candle"]),
  rateWindowMs: 60_000,
  rateMax: 60,
  softBan: Object.freeze({ blockThreshold: 8, windowMs: 300_000, banMs: 600_000 }),
  securityHeaders: Object.freeze({
    "x-bodyguard": BODYGUARD_VERSION,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
  }),
});

// Very small in-memory maps (per isolate). Acceptable for edge defense signals.
const rateBuckets = new Map();
const offenseBuckets = new Map();
const softBans = new Map();

const PROBE_RE = /(\.\.|%2e%2e|%252e|\/etc\/passwd|\/proc\/|\/win(dows)?\/|<|>|javascript:|onerror=|onload=|union\s+select|drop\s+table|insert\s+into|xp_cmdshell|\$\{|\{\{|%3c%3c|%00|\x00)/i;

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
  console.log(JSON.stringify(row));
  return row;
}

function noteOffense(key, reason) {
  const now = Date.now();
  let bucket = offenseBuckets.get(key);
  if (!bucket || now - bucket.start > DEFAULTS.softBan.windowMs) {
    bucket = { start: now, count: 0, lastReason: reason };
    offenseBuckets.set(key, bucket);
  }
  bucket.count += 1;
  bucket.lastReason = reason;
  if (bucket.count >= DEFAULTS.softBan.blockThreshold) {
    softBans.set(key, now + DEFAULTS.softBan.banMs);
    securityEvent("block", "soft_ban_applied", { key, count: bucket.count, until: softBans.get(key) });
  }
}

function isSoftBanned(key) {
  const until = softBans.get(key);
  if (!until) return false;
  if (Date.now() > until) {
    softBans.delete(key);
    return false;
  }
  return true;
}

export function applySecurityHeaders(response) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(DEFAULTS.securityHeaders)) {
    if (!headers.has(k)) headers.set(k, v);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export function detectProbe(request, url = new URL(request.url)) {
  const hay = `${url.pathname}?${url.search}`;
  if (PROBE_RE.test(hay)) {
    return { ok: false, status: 403, reason: "probe_pattern_blocked" };
  }
  // Reject weird encoded nulls / control chars in query
  if (/[\u0000-\u001f\u007f]/.test(url.search)) {
    return { ok: false, status: 400, reason: "control_chars_in_query" };
  }
  return { ok: true, status: 200, reason: "ok" };
}

export function scoreUserAgent(request) {
  const ua = (request.headers.get("user-agent") || "").trim();
  if (!ua) return { risk: "high", reason: "empty_user_agent" };
  if (/sqlmap|nikto|nmap|masscan|dirbuster|gobuster|zgrab|python-requests\/0\.|curl\/7\.[0-4]/i.test(ua)) {
    return { risk: "high", reason: "scanner_user_agent" };
  }
  return { risk: "low", reason: "ok" };
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
    if (!DEFAULTS.allowedApiPaths.has(url.pathname)) {
      return { ok: false, status: 404, reason: "api_route_not_found" };
    }
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
    securityEvent("block", "rate_limited", { path: new URL(request.url).pathname, count: bucket.count });
    return { ok: false, status: 429, reason: "rate_limited" };
  }
  return { ok: true, status: 200, reason: "ok", remaining: Math.max(0, max - bucket.count) };
}

export function publicError(status, reason, message) {
  return new Response(
    JSON.stringify({
      error: reason,
      message: String(message || reason).slice(0, 240),
      guard: "Bodyguard(Aria)",
      version: BODYGUARD_VERSION,
    }),
    {
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
        ...DEFAULTS.securityHeaders,
        ...(status === 429 || status === 403 ? { "retry-after": "60" } : {}),
      },
    },
  );
}

/**
 * Returns a Response to block the request, or null to allow.
 */
export function guardPublicRequest(request) {
  const url = new URL(request.url);
  const key = clientKey(request);

  if (isSoftBanned(key)) {
    securityEvent("block", "soft_banned", { path: url.pathname });
    return publicError(403, "soft_banned", "temporarily blocked");
  }

  const probe = detectProbe(request, url);
  if (!probe.ok) {
    noteOffense(key, probe.reason);
    securityEvent("block", probe.reason, { path: url.pathname });
    return publicError(probe.status, probe.reason, probe.reason);
  }

  const ua = scoreUserAgent(request);
  if (ua.risk === "high" && url.pathname.startsWith("/api/")) {
    // High-risk UA on API still allowed once, but counts toward offense if combined with other blocks.
    securityEvent("warn", ua.reason, { path: url.pathname });
  }

  const basic = validatePublicApiRequest(request, url);
  if (!basic.ok) {
    noteOffense(key, basic.reason);
    securityEvent("block", basic.reason, { path: url.pathname, method: request.method });
    return publicError(basic.status, basic.reason, basic.reason);
  }

  if (url.pathname.startsWith("/api/")) {
    const rate = checkRateLimit(request);
    if (!rate.ok) {
      noteOffense(key, rate.reason);
      return publicError(rate.status, rate.reason, "too many requests");
    }
  }

  return null;
}
