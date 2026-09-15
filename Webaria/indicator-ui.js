(() => {
  const STORAGE_KEY = 'webaria-indicator-visibility-v1';
  const defaults = Object.freeze({ ema20: true, ema50: true, ema200: false });
  const visibility = loadVisibility();
  let cacheKey = '';
  let cachedSeries = new Map();

  function loadVisibility() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {
        ema20: stored.ema20 !== false,
        ema50: stored.ema50 !== false,
        ema200: stored.ema200 === true,
      };
    } catch {
      return { ...defaults };
    }
  }

  function persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(visibility)); } catch {}
  }

  function emaSeries(candles, period) {
    const result = new Array(candles.length).fill(null);
    if (candles.length < period) return result;
    let current = candles.slice(0, period).reduce((sum, candle) => sum + candle.close, 0) / period;
    result[period - 1] = current;
    const alpha = 2 / (period + 1);
    for (let index = period; index < candles.length; index += 1) {
      current = (candles[index].close - current) * alpha + current;
      result[index] = current;
    }
    return result;
  }

  function refreshCache(candles) {
    const last = candles.at(-1);
    const key = `${candles.length}:${last?.time ?? ''}:${last?.close ?? ''}`;
    if (key === cacheKey) return;
    cacheKey = key;
    cachedSeries = new Map([20, 50, 200].map((period) => [period, emaSeries(candles, period)]));
  }

  function ensureOverlay() {
    const canvas = document.getElementById('indicator-overlay');
    const chart = document.getElementById('chart');
    if (!canvas || !chart) return null;
    canvas.width = chart.width;
    canvas.height = chart.height;
    canvas.style.width = `${chart.clientWidth}px`;
    canvas.style.height = `${chart.clientHeight}px`;
    return canvas;
  }

  function viewport(candles) {
    const total = candles.length;
    const count = Math.max(1, Math.min(total, Math.round(window.S?.visibleBars ?? total)));
    const offset = Math.max(0, Math.round(window.S?.offset ?? 0));
    const end = Math.max(count, total - offset);
    const start = Math.max(0, end - count);
    return candles.slice(start, end);
  }

  function draw() {
    const state = window.S;
    const chart = document.getElementById('chart');
    const overlay = ensureOverlay();
    if (!state || !chart || !overlay || !state.candles?.length) return;
    refreshCache(state.candles);
    const data = viewport(state.candles);
    if (!data.length) return;

    const ctx = overlay.getContext('2d');
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    const width = chart.clientWidth;
    const height = chart.clientHeight;
    const left = 12;
    const right = Math.max(62, Math.min(92, width * 0.075));
    const future = 56;
    const top = 38;
    const bottom = 26;
    const plotWidth = Math.max(1, width - left - right - future);
    const plotHeight = Math.max(1, height - top - bottom);
    let low = Math.min(...data.map((candle) => candle.low));
    let high = Math.max(...data.map((candle) => candle.high));
    const pad = Math.max(high - low, Number.EPSILON) * 0.045;
    low -= pad;
    high += pad;
    const y = (price) => top + ((high - price) / Math.max(high - low, Number.EPSILON)) * plotHeight;
    const x = (index) => left + plotWidth * (index + 0.5) / data.length;
    const indexByTime = new Map(state.candles.map((candle, index) => [Number(candle.time), index]));
    const styles = { 20: '#4fc3f7', 50: '#ffca28', 200: '#ab47bc' };

    for (const period of [20, 50, 200]) {
      if (!visibility[`ema${period}`]) continue;
      const series = cachedSeries.get(period);
      if (!series) continue;
      ctx.strokeStyle = styles[period];
      ctx.lineWidth = period === 200 ? 1.5 : 1.2;
      ctx.beginPath();
      let started = false;
      data.forEach((candle, visibleIndex) => {
        const sourceIndex = indexByTime.get(Number(candle.time));
        const value = sourceIndex == null ? null : series[sourceIndex];
        if (!Number.isFinite(value)) { started = false; return; }
        const px = x(visibleIndex);
        const py = y(value);
        if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      });
      ctx.stroke();
    }
    ctx.lineWidth = 1;
  }

  function renderSnapshot(snapshot) {
    const values = snapshot || {};
    const fields = {
      'indicator-ema20': values.ema20,
      'indicator-ema50': values.ema50,
      'indicator-ema200': values.ema200,
      'indicator-rsi14': values.rsi14,
      'indicator-atr14': values.atr14,
      'indicator-adx14': values.adx14,
      'indicator-macd': values.macd,
      'indicator-macd-signal': values.macd_signal,
      'indicator-macd-hist': values.macd_histogram,
    };
    for (const [id, value] of Object.entries(fields)) {
      const element = document.getElementById(id);
      if (!element) continue;
      element.textContent = Number.isFinite(Number(value))
        ? Number(value).toFixed(id.includes('rsi') || id.includes('adx') ? 2 : 5)
        : '—';
    }
  }

  function setupControls() {
    for (const period of [20, 50, 200]) {
      const button = document.getElementById(`indicator-ema-${period}`);
      if (!button) continue;
      const key = `ema${period}`;
      button.setAttribute('aria-pressed', visibility[key] ? 'true' : 'false');
      button.classList.toggle('active', visibility[key]);
      button.addEventListener('click', () => {
        visibility[key] = !visibility[key];
        button.setAttribute('aria-pressed', visibility[key] ? 'true' : 'false');
        button.classList.toggle('active', visibility[key]);
        persist();
        draw();
      });
    }
  }

  const overlay = document.createElement('canvas');
  overlay.id = 'indicator-overlay';
  overlay.setAttribute('aria-hidden', 'true');
  overlay.style.position = 'absolute';
  overlay.style.left = '0';
  overlay.style.top = '0';
  overlay.style.width = '100%';
  overlay.style.height = '100%';
  overlay.style.pointerEvents = 'none';
  overlay.style.zIndex = '3';
  document.getElementById('chartwrap')?.appendChild(overlay);

  window.WebariaIndicators = { renderSnapshot, draw, setupControls, visibility };
  setupControls();
  const loop = () => {
    if (window.S?.signal?.indicators) renderSnapshot(window.S.signal.indicators);
    draw();
    window.requestAnimationFrame(loop);
  };
  window.requestAnimationFrame(loop);
})();
