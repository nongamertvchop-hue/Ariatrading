(() => {
  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  const MIN_BARS = 28;
  const MAX_BARS = 140;
  const TARGET_PX_PER_BAR = 11;
  let userZoomed = false;
  let lastSize = { w: 0, h: 0 };

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const redraw = () => {
    if (typeof window.draw === 'function') window.draw();
  };

  function fitBarsToWidth() {
    const width = wrap.clientWidth;
    const count = state.candles?.length || 0;
    if (!width || !count) return;
    const usable = Math.max(240, width - 95);
    const target = clamp(Math.round(usable / TARGET_PX_PER_BAR), MIN_BARS, MAX_BARS);
    state.visibleBars = Math.min(count, target);
    state.offset = 0;
  }

  function resizeCanvas() {
    const rect = wrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    if (!userZoomed && (Math.abs(width - lastSize.w) > 24 || Math.abs(height - lastSize.h) > 24)) {
      fitBarsToWidth();
    }
    lastSize = { w: width, h: height };
    redraw();
  }

  function zoomAt(clientX, direction) {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const x = clamp(clientX - rect.left, 0, width);
    const oldCount = Math.max(1, Math.min(state.candles.length, Math.round(state.visibleBars || 60)));
    const total = state.candles.length;
    if (!total) return;
    const oldEnd = Math.max(oldCount, total - Math.max(0, Math.round(state.offset || 0)));
    const oldStart = Math.max(0, oldEnd - oldCount);
    const plotLeft = 12;
    const plotRight = Math.max(62, Math.min(92, width * 0.075));
    const ratio = clamp((x - plotLeft) / Math.max(1, width - plotLeft - plotRight), 0, 1);
    const anchor = oldStart + ratio * oldCount;
    const next = direction < 0 ? oldCount * 0.82 : oldCount * 1.22;
    const newCount = clamp(Math.round(next), MIN_BARS, Math.min(MAX_BARS, total));
    const maxStart = Math.max(0, total - newCount);
    const newStart = clamp(Math.round(anchor - ratio * newCount), 0, maxStart);
    state.visibleBars = newCount;
    state.offset = Math.max(0, total - (newStart + newCount));
    userZoomed = true;
    redraw();
  }

  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    zoomAt(event.clientX, event.deltaY > 0 ? 1 : -1);
  }, { passive: false, capture: true });

  const ro = new ResizeObserver(resizeCanvas);
  ro.observe(wrap);
  window.addEventListener('resize', resizeCanvas, { passive: true });

  window.WebariaChartUX = {
    fit: () => { userZoomed = false; fitBarsToWidth(); redraw(); },
    resetZoom: () => { userZoomed = false; fitBarsToWidth(); redraw(); }
  };

  // trading.js refreshes market data periodically and historically reset the viewport to 90 bars.
  // Preserve the user's zoom instead of allowing a background refresh to undo it.
  let lastVisible = state.visibleBars;
  setInterval(() => {
    if (!userZoomed) {
      lastVisible = state.visibleBars;
      return;
    }
    if (state.visibleBars === 90 && lastVisible !== 90) {
      state.visibleBars = lastVisible;
      redraw();
    } else {
      lastVisible = state.visibleBars;
    }
  }, 250);

  setTimeout(() => {
    fitBarsToWidth();
    resizeCanvas();
  }, 0);
})();
