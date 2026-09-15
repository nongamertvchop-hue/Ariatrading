(() => {
  const STORAGE_KEY = 'webaria-indicator-visibility-v1';
  const defaults = Object.freeze({ ema20: true, ema50: true, ema200: false });

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

  const visibility = loadVisibility();

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

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(visibility));
    } catch {
      // Indicator visibility is a UI preference; failure to persist it is non-fatal.
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
        window.S?.draw?.();
      });
    }
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
      element.textContent = Number.isFinite(Number(value)) ? Number(value).toFixed(id.includes('rsi') || id.includes('adx') ? 2 : 5) : '—';
    }
  }

  function drawOverlays(allCandles, visibleCandles, mapping, ctx) {
    if (!allCandles?.length || !visibleCandles?.length || !mapping) return;
    const periods = [20, 50, 200];
    const seriesByPeriod = new Map(periods.map((period) => [period, emaSeries(allCandles, period)]));
    const timeToSeriesIndex = new Map(allCandles.map((candle, index) => [Number(candle.time), index]));
    const styles = { 20: '#4fc3f7', 50: '#ffca28', 200: '#ab47bc' };

    for (const period of periods) {
      if (!visibility[`ema${period}`]) continue;
      const series = seriesByPeriod.get(period);
      ctx.strokeStyle = styles[period];
      ctx.lineWidth = period === 200 ? 1.5 : 1.2;
      ctx.beginPath();
      let started = false;
      visibleCandles.forEach((candle, visibleIndex) => {
        const sourceIndex = timeToSeriesIndex.get(Number(candle.time));
        const value = sourceIndex == null ? null : series[sourceIndex];
        if (!Number.isFinite(value)) {
          started = false;
          return;
        }
        const x = mapping.x(visibleIndex);
        const y = mapping.y(value);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
      ctx.lineWidth = 1;
    }
  }

  window.WebariaIndicators = { renderSnapshot, drawOverlays, setupControls, visibility };
  setupControls();
})();
