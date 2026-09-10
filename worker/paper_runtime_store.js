const DEFAULT_STATE = Object.freeze({
  contract: "aria.paper-runtime.v1",
  mode: "PAPER",
  lifecycle: "FLAT",
  running: false,
  halted: false,
  haltReason: "",
  heartbeat: null,
  lastBarTime: null,
  lastProcessedBarTime: null,
  account: { balance: 10000, equity: 10000, realizedPnl: 0, unrealizedPnl: 0, peakEquity: 10000, drawdown: 0, drawdownPct: 0, tradeCount: 0, winRate: 0 },
  position: null,
  pending: null,
  alerts: [],
  history: [],
  events: [],
  updatedAt: null,
});

const MAX_EVENTS = 300;
const MAX_HISTORY = 500;
const MAX_ALERTS = 100;

function sanitizeState(raw) {
  if (!raw || typeof raw !== "object") throw new Error("state payload must be an object");
  const state = {
    ...DEFAULT_STATE,
    ...raw,
    contract: "aria.paper-runtime.v1",
    mode: "PAPER",
    account: { ...DEFAULT_STATE.account, ...(raw.account || {}) },
    alerts: Array.isArray(raw.alerts) ? raw.alerts.slice(-MAX_ALERTS) : [],
    events: Array.isArray(raw.events) ? raw.events.slice(-MAX_EVENTS) : [],
    history: Array.isArray(raw.history) ? raw.history.slice(-MAX_HISTORY) : [],
    position: raw.position || null,
    pending: raw.pending || null,
    updatedAt: new Date().toISOString(),
  };
  if (!["FLAT", "SIGNAL", "APPROVED", "SUBMITTING", "ACKNOWLEDGED", "OPEN", "EXIT_PENDING", "CLOSED", "UNKNOWN", "HALT"].includes(state.lifecycle)) {
    throw new Error("invalid lifecycle");
  }
  if (state.heartbeat != null && !Number.isFinite(Date.parse(String(state.heartbeat)))) {
    throw new Error("invalid heartbeat");
  }
  return state;
}

export class PaperRuntimeStore {
  constructor(state) { this.state = state; }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "GET") {
      const stored = await this.state.storage.get("snapshot");
      const snapshot = stored || { ...DEFAULT_STATE, updatedAt: new Date().toISOString() };
      return Response.json({ ...snapshot, source: "durable-object" }, { headers: { "cache-control": "no-store" } });
    }
    if (request.method === "POST") {
      const body = await request.json();
      if (body.action === "recover") {
        const snapshot = (await this.state.storage.get("snapshot")) || { ...DEFAULT_STATE, updatedAt: new Date().toISOString() };
        return Response.json({ ...snapshot, recovered: true, source: "durable-object" }, { headers: { "cache-control": "no-store" } });
      }
      if (body.action === "heartbeat") {
        const snapshot = (await this.state.storage.get("snapshot")) || { ...DEFAULT_STATE };
        const heartbeat = new Date().toISOString();
        const next = { ...snapshot, contract: "aria.paper-runtime.v1", mode: "PAPER", heartbeat, updatedAt: heartbeat };
        await this.state.storage.put("snapshot", next);
        return Response.json({ ...next, source: "durable-object" }, { headers: { "cache-control": "no-store" } });
      }
      const snapshot = sanitizeState(body);
      await this.state.storage.put("snapshot", snapshot);
      return Response.json({ ok: true, contract: snapshot.contract, updatedAt: snapshot.updatedAt }, { headers: { "cache-control": "no-store" } });
    }
    if (request.method === "HEAD") return new Response(null, { status: 204 });
    return Response.json({ error: "method_not_allowed" }, { status: 405 });
  }
}

export { DEFAULT_STATE };
