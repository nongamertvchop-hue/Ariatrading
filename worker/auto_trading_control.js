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
      return json({
        ...current,
        mode: "DEMO_ONLY",
      });
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
      return json({
        ...next,
        mode: "DEMO_ONLY",
      });
    }

    if (request.method === "POST" && url.pathname === "/heartbeat") {
      const runtimeId = typeof request.headers.get("x-aria-runtime-id") === "string"
        ? request.headers.get("x-aria-runtime-id").slice(0, 120)
        : null;
      const next = {
        ...current,
        runtimeHeartbeatAt: nowIso(),
        runtimeId,
      };
      await this.ctx.storage.put("state", next);
      return json({
        ...next,
        mode: "DEMO_ONLY",
      });
    }

    return json({ error: "not found" }, 404);
  }
}
