// Public Bodyguard telemetry facade. It exposes only sanitized security metadata.
// Secrets, IPs, request bodies and broker credentials never cross this boundary.

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
      "x-webaria-bodyguard-contract": "bodyguard-telemetry-v1",
    },
  });
}

function classify(event) {
  const text = `${event?.event_type || ""} ${event?.payload?.reason || ""}`.toLowerCase();
  if (/execution|order|trade/.test(text)) return { category: "EXECUTION", severity: "CRITICAL" };
  if (/rate|quota|ban|abusive/.test(text)) return { category: "ABUSE", severity: "HIGH" };
  if (/cors|origin/.test(text)) return { category: "CORS", severity: "MEDIUM" };
  if (/probe|scanner|traversal|xss|sql|prototype|malformed|control|payload/.test(text)) return { category: "PROBE", severity: "HIGH" };
  if (/error|fail|timeout|disconnect/.test(text)) return { category: "RUNTIME", severity: "MEDIUM" };
  return { category: "RUNTIME", severity: "INFO" };
}

function sanitizeEvent(event) {
  const meta = classify(event);
  const payload = event?.payload && typeof event.payload === "object" ? event.payload : {};
  const reason = String(payload.reason || event?.event_type || "runtime event").slice(0, 180);
  const method = String(payload.method || "").toUpperCase().slice(0, 10);
  const path = String(payload.path || "").split("?")[0].slice(0, 120);
  const action = String(payload.action || "").slice(0, 80);
  return {
    at: event?.ts || null,
    level: meta.severity === "INFO" ? "info" : "block",
    severity: meta.severity,
    category: meta.category,
    reason,
    method,
    path,
    action,
  };
}

export async function onRequestGet(context) {
  const runtimeUrl = String(context.env?.MT5_RUNTIME_API_URL || "").trim().replace(/\/$/, "");
  const token = String(context.env?.RUNTIME_API_TOKEN || "").trim();
  if (!runtimeUrl || !token) {
    return json({
      guard: "Bodyguard(Aria)", version: "0.05.2", codename: "aegis-shield", mode: "fail-closed", posture: "DEGRADED",
      telemetry: { freshness: "UNAVAILABLE", delivery: "RUNTIME_NOT_CONFIGURED" }, counters: {}, recent_events: [],
      alerts: [{ level: "critical", code: "RUNTIME_TELEMETRY_UNAVAILABLE", message: "MT5 runtime telemetry bridge is not configured" }],
    }, 503);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const headers = { accept: "application/json", authorization: `Bearer ${token}`, "cache-control": "no-cache" };
    const [eventResponse, healthResponse] = await Promise.all([
      fetch(`${runtimeUrl}/events?limit=100`, { signal: controller.signal, headers }),
      fetch(`${runtimeUrl}/health`, { signal: controller.signal, headers }),
    ]);
    let body;
    try { body = await eventResponse.json(); } catch { throw new Error(`runtime returned invalid events JSON (HTTP ${eventResponse.status})`); }
    if (!eventResponse.ok || !Array.isArray(body?.events)) throw new Error(body?.message || `runtime events HTTP ${eventResponse.status}`);
    let health = {};
    try { health = await healthResponse.json(); } catch { /* event data remains useful */ }

    const events = body.events.map(sanitizeEvent);
    const counters = {
      allowed: events.filter(e => e.level === "info").length,
      blocked: events.filter(e => e.level === "block").length,
      rate_limited: events.filter(e => e.category === "ABUSE").length,
      probes: events.filter(e => e.category === "PROBE").length,
      soft_bans: events.filter(e => /ban/i.test(e.reason)).length,
      status_calls: events.filter(e => /status|health/i.test(e.reason)).length,
      execution_attempts: events.filter(e => e.category === "EXECUTION").length,
      cors_blocked: events.filter(e => e.category === "CORS").length,
      payloads_blocked: events.filter(e => /payload/i.test(e.reason)).length,
    };
    const heartbeat = health?.heartbeat_at ? Date.parse(health.heartbeat_at) : NaN;
    const heartbeatAge = Number.isFinite(heartbeat) ? Math.max(0, Date.now() - heartbeat) : Infinity;
    const latest = events[0]?.at ? Date.parse(events[0].at) : NaN;
    const eventAge = Number.isFinite(latest) ? Math.max(0, Date.now() - latest) : Infinity;
    const stale = heartbeatAge > 10000 || (!Number.isFinite(heartbeatAge) && eventAge > 10000);
    const posture = events.some(e => e.severity === "CRITICAL") ? "CRITICAL" : events.some(e => e.severity === "HIGH") ? "ELEVATED" : (stale ? "DEGRADED" : "HEALTHY");
    return json({
      guard: "Bodyguard(Aria)", version: "0.05.2", codename: "aegis-shield", mode: "enforce", posture,
      started_at: null,
      telemetry: { freshness: stale ? "STALE" : "LIVE", delivery: "DURABLE_RUNTIME_SQLITE", event_window: events.length, heartbeat_at: health?.heartbeat_at || null },
      counters, recent_events: events,
      alerts: stale ? [{ level: "critical", code: "TELEMETRY_STALE", message: "Runtime heartbeat is stale or unavailable" }] : [],
    });
  } catch (error) {
    return json({
      guard: "Bodyguard(Aria)", version: "0.05.2", codename: "aegis-shield", mode: "fail-closed", posture: "DEGRADED",
      telemetry: { freshness: "UNAVAILABLE", delivery: "RUNTIME_ERROR" }, counters: {}, recent_events: [],
      alerts: [{ level: "critical", code: "RUNTIME_TELEMETRY_ERROR", message: error?.name === "AbortError" ? "Runtime telemetry request timed out" : String(error?.message || "Runtime telemetry unavailable").slice(0, 180) }],
    }, 503);
  } finally {
    clearTimeout(timer);
  }
}
