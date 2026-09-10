/* Webaria live market bridge.
 * Keeps the existing chart renderer stable while replacing the legacy signal
 * candle source with canonical live market data and polling the live quote.
 */
(function () {
  'use strict';

  const originalFetch = window.fetch.bind(window);
  const POLL_MS = 3000;

  function signalParts(input) {
    const raw = typeof input === 'string' ? input : input?.url;
    if (!raw) return null;
    try {
      const url = new URL(raw, window.location.origin);
      if (!/\/api\/signal(?:[/?]|$)/.test(url.pathname)) return null;
      return {
        symbol: url.searchParams.get('symbol') || 'EUR/USD',
        timeframe: url.searchParams.get('timeframe') || '15m',
      };
    } catch {
      return null;
    }
  }

  async function liveMarket(symbol, timeframe) {
    const url = `/api/market?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const response = await originalFetch(url, { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok || payload.source !== 'twelve-data') {
      throw new Error(payload.message || `Live market data unavailable (HTTP ${response.status})`);
    }
    return payload;
  }

  function normalizeTime(value) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 0 && Math.abs(n) < 1e11) return n * 1000;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : value;
  }

  function normalizeCandles(candles) {
    return (Array.isArray(candles) ? candles : []).map((c) => ({
      time: normalizeTime(c.time ?? c.datetime),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    }));
  }

  function status(text, live) {
    const node = document.getElementById('status');
    if (!node) return;
    node.textContent = text;
    node.dataset.marketState = live ? 'LIVE' : 'UNAVAILABLE';
  }

  function renderLiveQuote(payload) {
    const price = Number(payload.price);
    const quote = document.getElementById('quote');
    if (quote && Number.isFinite(price)) quote.textContent = price.toFixed(Math.abs(price) >= 20 ? 3 : 5);

    const legend = document.getElementById('legend');
    const symbol = payload.symbol || window.S?.symbol || 'EUR/USD';
    const tf = payload.timeframe || window.S?.tf || '15m';
    const candle = window.S?.candles?.at(-1);
    if (legend && candle) {
      const f = (v) => Number.isFinite(Number(v)) ? Number(v).toFixed(Math.abs(Number(v)) >= 20 ? 3 : 5) : '—';
      legend.innerHTML = `<div class="title">${symbol} · ${tf} · LIVE</div><div class="ohlc">O ${f(candle.open)} H ${f(candle.high)} L ${f(candle.low)} C ${f(price)}</div>`;
    }
  }

  window.fetch = async function webariaLiveFetch(input, init) {
    const parts = signalParts(input);
    if (!parts) return originalFetch(input, init);

    try {
      const payload = await liveMarket(parts.symbol, parts.timeframe);
      return new Response(JSON.stringify({
        symbol: payload.symbol,
        timeframe: payload.timeframe,
        candles: normalizeCandles(payload.candles),
        live_candle: payload.live_candle,
        price: Number(payload.price),
        source: payload.source,
        generated_at: payload.generated_at,
        signal: 'WAIT',
        direction: 'WAIT',
        state: 'LIVE_DATA_ONLY',
        reason: 'Live market data connected; strategy evaluation remains paper-only.',
        structure_bias: '—',
        breakout_state: '—',
        score: null,
        zone: null,
        entry_reference: null,
        stop_reference: null,
      }), {
        status: 200,
        headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
      });
    } catch (error) {
      return new Response(JSON.stringify({
        error: 'live_data_unavailable',
        message: error?.message || 'Live market data unavailable',
        source: 'unavailable',
        candles: [],
      }), {
        status: 503,
        headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
      });
    }
  };

  async function poll() {
    const state = window.S;
    if (!state?.symbol || !state?.tf) return;

    try {
      const payload = await liveMarket(state.symbol, state.tf);
      const candles = normalizeCandles(payload.candles);
      if (!candles.length) throw new Error('No completed market candles returned');

      state.candles = candles;
      state.price = Number(payload.price);
      state.signal = {
        ...(state.signal || {}),
        symbol: payload.symbol,
        timeframe: payload.timeframe,
        source: payload.source,
        price: state.price,
        live_candle: payload.live_candle,
        signal: 'WAIT',
        direction: 'WAIT',
        state: 'LIVE_DATA_ONLY',
        reason: 'Live market data connected; strategy evaluation remains paper-only.',
        structure_bias: '—',
        breakout_state: '—',
        score: null,
        zone: null,
        entry_reference: null,
        stop_reference: null,
      };
      renderLiveQuote(payload);
      status(`LIVE · ${new Date().toLocaleTimeString()}`, true);
      window.dispatchEvent(new Event('resize'));
    } catch (error) {
      status(`LIVE DATA UNAVAILABLE · ${error?.message || 'provider error'}`, false);
    }
  }

  window.WebariaLiveMarket = Object.freeze({ poll });
  setTimeout(poll, 0);
  setInterval(poll, POLL_MS);
})();
