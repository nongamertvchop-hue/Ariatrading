(() => {
  "use strict";

  const TOKEN_KEY = "ariatrading-demo-control-token";
  const POLL_MS = 1500;
  const runtime = {
    state: null,
    busy: false,
  };

  function qs(id) {
    return document.getElementById(id);
  }

  function ensureControls() {
    if (qs("autoTradingToggle")) return;

    const style = document.createElement("style");
    style.textContent = `
      #ariaAutoTrading { display:inline-flex; align-items:center; gap:6px; }
      #autoTradingToggle { font-weight:700; min-width:96px; border-radius:999px; }
      #autoTradingToggle.aria-on { border-color:#2f7b5a; background:#173d2e; }
      #autoTradingToggle.aria-off { border-color:#5f6670; background:#20252c; }
      #autoTradingToggle.aria-error { border-color:#88434e; background:#432025; }
      #autoTradingRuntime { font-size:10px; color:#89929e; white-space:nowrap; }
      @media (max-width:720px) {
        #ariaAutoTrading { flex:0 0 auto; }
        #autoTradingRuntime { display:none; }
        #autoTradingToggle { min-width:90px; padding:7px 8px; }
      }
    `;
    document.head.appendChild(style);

    const refresh = qs("refresh");
    const group = document.createElement("div");
    group.id = "ariaAutoTrading";
    group.innerHTML = `
      <button id="autoTradingToggle" class="aria-off" type="button" aria-pressed="false" title="Demo Auto Trading is OFF">AUTO OFF</button>
      <span id="autoTradingRuntime">DEMO · OFFLINE</span>
    `;
    if (refresh && refresh.parentNode) refresh.parentNode.insertBefore(group, refresh);
    else document.querySelector("header")?.appendChild(group);
  }

  function getToken(promptUser = false) {
    let token = localStorage.getItem(TOKEN_KEY) || "";
    if (!token && promptUser) {
      token = window.prompt("Enter DEMO_CONTROL_TOKEN");
      if (token) {
        token = token.trim();
        if (token) localStorage.setItem(TOKEN_KEY, token);
      }
    }
    return token;
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  async function controlRequest(method, body) {
    const token = getToken(true);
    if (!token) throw new Error("missing control token");
    const headers = {
      accept: "application/json",
      authorization: `Bearer ${token}`,
    };
    if (body !== undefined) headers["content-type"] = "application/json";

    const response = await fetch("/api/auto-trading", {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });

    if (response.status === 401) {
      clearToken();
      throw new Error("unauthorized");
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || payload.mode !== "DEMO_ONLY") {
      throw new Error(payload?.error || `control request failed (${response.status})`);
    }
    return payload;
  }

  async function fetchState() {
    return controlRequest("GET");
  }

  async function setState(enabled) {
    return controlRequest("POST", { enabled, source: "webaria-ui" });
  }

  function render() {
    const button = qs("autoTradingToggle");
    const runtimeBadge = qs("autoTradingRuntime");
    if (!button || !runtimeBadge) return;

    if (!runtime.state) {
      button.textContent = "AUTO ?";
      button.className = "aria-error";
      button.disabled = runtime.busy;
      button.title = "Auto Trading control is not available";
      runtimeBadge.textContent = "DEMO · CONTROL ERROR";
      return;
    }

    const enabled = runtime.state.enabled === true;
    const online = runtime.state.runtime_online === true;
    button.textContent = enabled ? "AUTO ON" : "AUTO OFF";
    button.className = enabled ? "aria-on" : "aria-off";
    button.setAttribute("aria-pressed", String(enabled));
    button.disabled = runtime.busy;
    button.title = enabled
      ? "Demo Auto Trading ON — click to disable new automatic entries"
      : "Demo Auto Trading OFF — click to enable automatic entries";
    runtimeBadge.textContent = `DEMO · ${online ? "ONLINE" : "OFFLINE"}`;
  }

  async function refreshState() {
    if (runtime.busy) return;
    try {
      runtime.state = await fetchState();
      render();
    } catch (error) {
      runtime.state = null;
      render();
    }
  }

  async function toggle() {
    if (runtime.busy) return;
    const currentEnabled = runtime.state?.enabled === true;
    runtime.busy = true;
    render();
    try {
      runtime.state = await setState(!currentEnabled);
    } catch (error) {
      // A 401 clears the stored token; the next click will request it again.
      runtime.state = null;
    } finally {
      runtime.busy = false;
      render();
      await refreshState();
    }
  }

  function init() {
    ensureControls();
    qs("autoTradingToggle")?.addEventListener("click", toggle);
    void refreshState();
    window.setInterval(refreshState, POLL_MS);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
