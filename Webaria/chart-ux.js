(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  // Keep viewport geometry identical to trading.js. This file owns sizing and
  // public viewport controls only; candle interaction remains in trading.js.
  const MIN_BARS = 18;
  const MAX_BARS = 140;
  const TARGET_PX_PER_BAR = 20;
  const LEFT_AXIS = 12;
  const FUTURE_SPACE = 56;
  const MIN_RIGHT_AXIS = 62;

  let lastWidth = 0;
  let lastHeight = 0;
  let scheduled = false;

  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  const candleCount = () => Array.isArray(state.candles) ? state.candles.length : 0;
  const rightAxis = width => Math.max(MIN_RIGHT_AXIS, Math.min(92, width * 0.075));
  const plotWidth = width => Math.max(1, width - LEFT_AXIS - rightAxis(width) - FUTURE_SPACE);

  function redraw() {
    if (typeof window.draw === 'function') window.draw();
  }

  function fit() {
    const total = candleCount();
    const width = Math.max(1, wrap.clientWidth);
    if (!total || width < 1) return;

    const target = Math.round(plotWidth(width) / TARGET_PX_PER_BAR);
    state.visibleBars = clamp(target, MIN_BARS, Math.min(MAX_BARS, total));
    state.offset = 0;
    state._userViewport = false;
    redraw();
  }

  function normalizeViewport() {
    const total = candleCount();
    if (!total) return;

    const maxVisible = Math.min(MAX_BARS, total);
    state.visibleBars = clamp(
      Math.round(Number(state.visibleBars) || maxVisible),
      Math.min(MIN_BARS, maxVisible),
      maxVisible
    );
    state.offset = clamp(
      Math.round(Number(state.offset) || 0),
      0,
      Math.max(0, total - state.visibleBars)
    );
  }

  function resizeCanvas() {
    const rect = wrap.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const pixelWidth = Math.max(1, Math.round(width * dpr));
    const pixelHeight = Math.max(1, Math.round(height * dpr));

    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }

    const context = canvas.getContext('2d');
    if (context) context.setTransform(dpr, 0, 0, dpr, 0, 0);

    const changed = Math.abs(width - lastWidth) > 2 || Math.abs(height - lastHeight) > 2;
    lastWidth = width;
    lastHeight = height;

    // Resizing must not destroy manual zoom/pan. Automatic fitting is only
    // applied before the user takes control of the viewport.
    if (changed && !state.dragging && !state.draft && !state._userViewport) fit();
    normalizeViewport();
    redraw();
  }

  window.WebariaChartUX = {
    fit,
    resetZoom: fit,
    zoomIn() {
      if (typeof window.setZoom !== 'function') return;
      window.setZoom(state.visibleBars * 0.82);
      state._userViewport = true;
    },
    zoomOut() {
      if (typeof window.setZoom !== 'function') return;
      window.setZoom(state.visibleBars * 1.22);
      state._userViewport = true;
    },
    resize: resizeCanvas
  };

  const fitButton = document.getElementById('fit');
  if (fitButton) fitButton.onclick = fit;

  const resetButton = document.getElementById('reset');
  if (resetButton) {
    resetButton.onclick = () => {
      state.selectedDrawing = null;
      fit();
    };
  }

  const ro = typeof ResizeObserver === 'function'
    ? new ResizeObserver(() => {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
          scheduled = false;
          resizeCanvas();
        });
      })
    : null;

  if (ro) ro.observe(wrap);

  window.addEventListener('resize', () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      resizeCanvas();
    });
  }, { passive: true });

  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  canvas.style.webkitUserSelect = 'none';

  setTimeout(resizeCanvas, 0);
})();
