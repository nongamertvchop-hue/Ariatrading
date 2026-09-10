/* Webaria performance layer: keep the first paint responsive without changing strategy logic. */
(function (root) {
  'use strict';

  const nativeFetch = root.fetch.bind(root);
  const inflight = new Map();
  const cache = new Map();
  const SIGNAL_TTL = 1500;
  const PRICE_TTL = 2500;
  const WATCH_BATCH = 2;

  function apiKey(input) {
    try {
      const url = new URL(typeof input === 'string' ? input : input.url, root.location.href);
      if (url.origin !== root.location.origin) return null;
      if (!url.pathname.startsWith('/api/')) return null;
      if (url.pathname !== '/api/signal' && url.pathname !== '/api/price') return null;
      url.searchParams.sort();
      return url.toString();
    } catch (_) {
      return null;
    }
  }

  root.fetch = function cachedApiFetch(input, init) {
    const key = apiKey(input);
    const method = String(init?.method || (typeof input !== 'string' ? input.method : 'GET')).toUpperCase();
    if (!key || method !== 'GET') return nativeFetch(input, init);

    const now = Date.now();
    const ttl = key.includes('/api/signal') ? SIGNAL_TTL : PRICE_TTL;
    const hit = cache.get(key);
    if (hit && now - hit.time < ttl) return hit.promise.then(response => response.clone());

    const existing = inflight.get(key);
    if (existing) return existing.then(response => response.clone());

    const promise = nativeFetch(input, init).then(response => {
      if (response.ok) cache.set(key, { time: Date.now(), promise: Promise.resolve(response.clone()) });
      return response;
    }).finally(() => inflight.delete(key));

    inflight.set(key, promise);
    return promise.then(response => response.clone());
  };

  function lazyWatch() {
    const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD'];
    const current = root.S?.symbol || document.getElementById('symbol')?.value || symbols[0];
    const state = root.S;
    if (!state) return;

    const fetchOne = async symbol => {
      try {
        const response = await nativeFetch(`/api/price?symbol=${encodeURIComponent(symbol)}`, { cache: 'no-store' });
        if (!response.ok) return;
        const payload = await response.json();
        const price = Number(payload?.price);
        if (!Number.isFinite(price)) return;
        const previous = state.watch[symbol]?.price;
        state.watch[symbol] = { price, pct: previous ? ((price - previous) / previous) * 100 : 0 };
      } catch (_) {
        // Watchlist is non-critical; keep the last known value on transient failure.
      }
    };

    void fetchOne(current).then(() => {
      if (typeof root.renderWatch === 'function') root.renderWatch();
    });

    const rest = symbols.filter(symbol => symbol !== current);
    let cursor = 0;
    const pump = () => {
      const batch = rest.slice(cursor, cursor + WATCH_BATCH);
      cursor += WATCH_BATCH;
      if (!batch.length) return;
      Promise.all(batch.map(fetchOne)).then(() => {
        if (typeof root.renderWatch === 'function') root.renderWatch();
        if (cursor < rest.length) root.setTimeout(pump, 120);
      });
    };
    root.setTimeout(pump, 350);
  }

  if (typeof root.updateWatch === 'function') root.updateWatch = lazyWatch;
})(window);
