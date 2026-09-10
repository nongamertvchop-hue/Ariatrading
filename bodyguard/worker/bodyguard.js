/**
 * Bodyguard(Aria) v0.05.1 — aegis-shield
 *
 * Enforcement, audit counters, alert thresholds, prototype pollution protection,
 * execution boundary isolation, strict CORS defense, and bounded in-memory state.
 */

export const BODYGUARD_VERSION = "0.05.1";

const DEFAULTS = Object.freeze({
  allowedMethods: ["GET", "HEAD", "OPTIONS"],
  maxQueryLength: 512,
  maxBodyBytes: 8192,
  maxNestingDepth: 5,
  maxRateBuckets: 4096,
  maxOffenseBuckets: 4096,
  maxSoftBans: 4096,
  symbolPattern: /^[A-Z]{3}\/[A-Z]{3}$/,
  allowedTimeframes: new Set(["1m", "5m", "15m", "30m", "1h", "4h", "1D"]),
  allowedApiPaths: new Set([
    "/api/signal",
    "/api/price",
    "/api/live-candle",
    "/api/market",
    "/api/bodyguard/status",
  ]),
  forbiddenExecutionPaths: new Set([
    "/api/order",
    "/api/execute",
    "/api/trade",
    "/api/buy",
    "/api/sell",
    "/api/mt5",
  ]),
  allowedOrigins: new Set([
    "https://webaria.pages.dev",
    "https://ariatrading.pages.dev",
    "http://localhost:8787",
    "http://127.0.0.1:8787",
  ]),
  rateWindowMs: 60_000,
  rateMax: 60,
  softBan: Object.freeze({ blockThreshold: 8, windowMs: 300_000, banMs: 600_000 }),
  alerts: Object.freeze({
    probeWarn: 5,
    blockWarn: 20,
    rateLimitWarn: 10,
    softBanWarn: 1,
    executionAttemptWarn: 1,
    corsWarn: 10,
  }),
  securityHeaders: Object.freeze({
    "x-bodyguard": BODYGUARD_VERSION,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "interest-cohort=()",
  }),
});

const rateBuckets = new Map();
const offenseBuckets = new Map();
const softBans = new Map();

const audit = {
  startedAt: new Date().toISOString(),
  allowed: 0,
  blocked: 0,
  rateLimited: 0,
  probes: 0,
  softBans: 0,
  statusCalls: 0,
  executionAttempts: 0,
  corsBlocked: 0,
  payloadsBlocked: 0,
};

const PROBE_RE = /(\.\.|%2e%2e|%252e|\/etc\/passwd|\/proc\/|\/win(dows)?\/|<|>|javascript:|onerror=|onload=|union\s+select|drop\s+table|insert\s+into|\bexec\b|xp_cmdshell|\$\{|\{\{|%3c%3c|%00)/i;
const PROTO_POLLUTION_RE = /(__proto__|constructor|prototype|\$where)/i;
const PUBLIC_MESSAGES = Object.freeze({
  cors_origin_rejected: "origin not permitted",
  soft_banned: "temporarily blocked",
  rate_limited: "too many requests",
  probe_pattern_blocked: "request rejected",
  double_encoded_probe_blocked: "request rejected",
  malformed_uri_sequence: "request rejected",
  control_chars_in_query: "request rejected",
  prototype_pollution_blocked: "request rejected",
  payload_nesting_too_deep: "request rejected",
  method_not_allowed: "method not allowed",
  query_too_long: "request rejected",
  execution_surface_forbidden: "request rejected",
  api_route_not_found: "not found",
  invalid_symbol: "invalid symbol",
  invalid_timeframe: "invalid timeframe",
});

function clientKey(request) {
  return request.headers.get("cf-connecting-ip") || request.headers.get("x-forwarded-for") || "unknown";
}

function evictOldest(map, maxSize) {
  if (map.size < maxSize) return;
  const oldest = map.keys().next().value;
  if (oldest !== undefined) map.delete(oldest);
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
    evictOldest(offenseBuckets, DEFAULTS.maxOffenseBuckets);
    bucket = { start: now, count: 0, lastReason: reason };
    offenseBuckets.set(key, bucket);
  }
  bucket.count += 1;
  bucket.lastReason = reason;
  if (bucket.count >= DEFAULTS.softBan.blockThreshold) {
    evictOldest(softBans, DEFAULTS.maxSoftBans);
    softBans.set(key, now + DEFAULTS.softBan.banMs);
    audit.softBans += 1;
    securityEvent("block", "soft_ban_applied", { count: bucket.count });
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

export function getCorsHeaders(request) {
  const origin = request.headers.get("origin");
  const headers = {};
  if (origin && DEFAULTS.allowedOrigins.has(origin.trim())) {
    headers["access-control-allow-origin"] = origin.trim();
    headers["access-control-allow-methods"] = "GET, HEAD, OPTIONS";
    headers["access-control-allow-headers"] = "content-type, x-bodyguard, x-requested-with";
    headers["access-control-max-age"] = "86400";
    headers["vary"] = "Origin";
  }
  return headers;
}

export function handleCorsPreflight(request) {
  const origin = request.headers.get("origin");
  if (!origin) return null;

  if (!DEFAULTS.allowedOrigins.has(origin.trim())) {
    audit.corsBlocked += 1;
    securityEvent("block", "cors_origin_rejected", { origin: origin.trim().slice(0, 200) });
    return publicError(403, "cors_origin_rejected");
  }

  return new Response(null, {
    status: 204,
    headers: {
      ...DEFAULTS.securityHeaders,
      ...getCorsHeaders(request),
    },
  });
}

export function applySecurityHeaders(response, request = null) {
  const headers = new Headers(response.headers);
  for (const [k, v] of Object.entries(DEFAULTS.securityHeaders)) {
    if (!headers.has(k)) headers.set(k, v);
  }
  if (request) {
    const cors = getCorsHeaders(request);
    for (const [k, v] of Object.entries(cors)) {
      headers.set(k, v);
    }
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export function detectProbe(request, url = new URL(request.url)) {
  const hay = `${url.pathname}?${url.search}`;
  if (PROBE_RE.test(hay)) return { ok: false, status: 403, reason: "probe_pattern_blocked" };

  try {
    const once = decodeURIComponent(hay);
    const twice = decodeURIComponent(once);
    if (once !== twice && PROBE_RE.test(twice)) {
      return { ok: false, status: 403, reason: "double_encoded_probe_blocked" };
    }
  } catch (_) {
    return { ok: false, status: 400, reason: "malformed_uri_sequence" };
  }

  if (/[\u0000-\u001f\u007f]/.test(url.search)) {
    return { ok: false, status: 400, reason: "control_chars_in_query" };
  }
  return { ok: true, status: 200, reason: "ok" };
}

export function detectPrototypePollution(data, depth = 1) {
  if (depth > DEFAULTS.maxNestingDepth) {
    return { ok: false, reason: "payload_nesting_too_deep" };
  }
  if (data && typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      if (PROTO_POLLUTION_RE.test(k)) {
        return { ok: false, reason: "prototype_pollution_blocked", key: k };
      }
      const child = detectPrototypePollution(v, depth + 1);
      if (!child.ok) return child;
    }
  }
  return { ok: true, reason: "ok" };
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

  for (const forbidden of DEFAULTS.forbiddenExecutionPaths) {
    if (url.pathname.toLowerCase().startsWith(forbidden)) {
      audit.executionAttempts += 1;
      return { ok: false, status: 403, reason: "execution_surface_forbidden" };
    }
  }

  if (url.pathname.startsWith("/api/")) {
    if (!DEFAULTS.allowedApiPaths.has(url.pathname)) {
      return { ok: false, status: 404, reason: "api_route_not_found" };
    }
    if (url.pathname === "/api/bodyguard/status") {
      return { ok: true, status: 200, reason: "ok" };
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
    evictOldest(rateBuckets, DEFAULTS.maxRateBuckets);
    bucket = { start: now, count: 0 };
    rateBuckets.set(key, bucket);
  }
  bucket.count += 1;
  if (bucket.count > max) {
    audit.rateLimited += 1;
    securityEvent("block", "rate_limited", { path: new URL(request.url).pathname, count: bucket.count });
    return { ok: false, status: 429, reason: "rate_limited" };
  }
  return { ok: true, status: 200, reason: "ok", remaining: Math.max(0, max - bucket.count) };
}

export function publicError(status, reason) {
  audit.blocked += 1;
  const safeMessage = PUBLIC_MESSAGES[reason] || "request rejected";
  return new Response(JSON.stringify({
    error: reason,
    message: safeMessage,
    guard: "Bodyguard(Aria)",
    version: BODYGUARD_VERSION,
  }), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...DEFAULTS.securityHeaders,
      ...(status === 429 || status === 403 ? { "retry-after": "60" } : {}),
    },
  });
}

function buildAlerts(counters) {
  const alerts = [];
  if (counters.probes >= DEFAULTS.alerts.probeWarn) {
    alerts.push({ level: "warn", code: "probes_elevated", message: `probes=${counters.probes}` });
  }
  if (counters.blocked >= DEFAULTS.alerts.blockWarn) {
    alerts.push({ level: "warn", code: "blocks_elevated", message: `blocked=${counters.blocked}` });
  }
  if (counters.rate_limited >= DEFAULTS.alerts.rateLimitWarn) {
    alerts.push({ level: "warn", code: "rate_limits_elevated", message: `rate_limited=${counters.rate_limited}` });
  }
  if (counters.soft_bans >= DEFAULTS.alerts.softBanWarn) {
    alerts.push({ level: "warn", code: "soft_bans_present", message: `soft_bans=${counters.soft_bans}` });
  }
  if (counters.execution_attempts >= DEFAULTS.alerts.executionAttemptWarn) {
    alerts.push({ level: "critical", code: "execution_attempt_blocked", message: `attempts=${counters.execution_attempts}` });
  }
  if (counters.cors_blocked >= DEFAULTS.alerts.corsWarn) {
    alerts.push({ level: "warn", code: "cors_rejections_elevated", message: `cors_blocked=${counters.cors_blocked}` });
  }
  return alerts;
}

export function getStatusPayload() {
  audit.statusCalls += 1;
  const counters = {
    allowed: audit.allowed,
    blocked: audit.blocked,
    rate_limited: audit.rateLimited,
    probes: audit.probes,
    soft_bans: audit.softBans,
    status_calls: audit.statusCalls,
    execution_attempts: audit.executionAttempts,
    cors_blocked: audit.corsBlocked,
    payloads_blocked: audit.payloadsBlocked,
  };
  return {
    guard: "Bodyguard(Aria)",
    version: BODYGUARD_VERSION,
    codename: "aegis-shield",
    mode: "enforce",
    scope: "defensive-only",
    execution: "ISOLATED_NONE",
    posture: counters.execution_attempts > 0 ? "UNDER_ATTACK" : (counters.probes > 10 ? "ELEVATED" : "HEALTHY"),
    started_at: audit.startedAt,
    counters,
    alerts: buildAlerts(counters),
    note: "Aggregate counters only. No IPs, secrets, or personal data.",
  };
}

export function statusResponse() {
  return new Response(JSON.stringify(getStatusPayload()), {
    status: 200,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...DEFAULTS.securityHeaders,
    },
  });
}

export function guardPublicRequest(request) {
  const url = new URL(request.url);
  const key = clientKey(request);

  if (request.method === "OPTIONS") {
    return handleCorsPreflight(request);
  }

  if (isSoftBanned(key)) {
    securityEvent("block", "soft_banned", { path: url.pathname });
    return publicError(403, "soft_banned");
  }

  const probe = detectProbe(request, url);
  if (!probe.ok) {
    audit.probes += 1;
    noteOffense(key, probe.reason);
    securityEvent("block", probe.reason, { path: url.pathname });
    return publicError(probe.status, probe.reason);
  }

  const ua = scoreUserAgent(request);
  if (ua.risk === "high" && url.pathname.startsWith("/api/")) {
    securityEvent("warn", ua.reason, { path: url.pathname });
  }

  const basic = validatePublicApiRequest(request, url);
  if (!basic.ok) {
    noteOffense(key, basic.reason);
    securityEvent("block", basic.reason, { path: url.pathname, method: request.method });
    return publicError(basic.status, basic.reason);
  }

  if (url.pathname.startsWith("/api/")) {
    const rate = checkRateLimit(request);
    if (!rate.ok) {
      noteOffense(key, rate.reason);
      return publicError(rate.status, rate.reason);
    }
  }

  audit.allowed += 1;
  return null;
}
