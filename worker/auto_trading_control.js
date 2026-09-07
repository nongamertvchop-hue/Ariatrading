import { DurableObject } from "cloudflare:workers";

const DEFAULT_STATE = Object.freeze({
  enabled: false,
  updatedAt: null,
  updatedBy: null,
  runtimeHeartbeatAt: null,
  runtimeId: null,
});

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function nowIso() {
  return new Date().toISOString();
}

function withDerivedState(state) {
  let runtimeOnline = false;
  if (state.runtimeHeartbeatAt) {
    const heartbeat = Date.parse(state.runtimeHeartbeatAt);
    runtimeOnline = Number.isFinite(heartbeat) && Date.now() - heartbeat <= 15_000;
  }
  return {
    ...state,
    mode: "DEMO_ONLY",
    runtimeOnline,
  };
}

export class AutoTradingControl extends DurableObject {
  async _state() {
    return {
      ...DEFAULT_STATE,
      ...((await this.ctx.storage.get("state")) || {}),
    };
  }

  async fetch(request) {
    const url = new URL(request.url);
    const current = await this._state();

    if (request.method === "GET" && url.pathname === "/state") {
      return json(withDerivedState(current));
    }

    if (request.method === "POST" && url.pathname === "/state") {
      let payload;
      try {
        payload = await request.json();
      } catch {
        return json({ error: "invalid JSON body" }, 400);
      }
      if (typeof payload.enabled !== "boolean") {
        return json({ error: "enabled must be boolean" }, 400);
      }

      const next = {
        ...current,
        enabled: payload.enabled,
        updatedAt: nowIso(),
        updatedBy: typeof payload.source === "string" && payload.source ? payload.source.slice(0, 80) : "webaria",
      };
      await this.ctx.storage.put("state", next);
      return json(withDerivedState(next));
    }

    if (request.method === "POST" && url.pathname === "/heartbeat") {
      const rawRuntimeId = request.headers.get("x-aria-runtime-id");
      const runtimeId = rawRuntimeId ? rawRuntimeId.slice(0, 120) : null;
      const next = {
        ...current,
        runtimeHeartbeatAt: nowIso(),
        runtimeId,
      };
      await this.ctx.storage.put("state", next);
      return json(withDerivedState(next));
    }

    return json({ error: "not found" }, 404);
  }
}
