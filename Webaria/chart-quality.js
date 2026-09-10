/* Webaria chart quality layer: keep the canvas bitmap aligned with its CSS size and fit candles to the real plot width. */
(function () {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  if (!canvas || !wrap) return;

  const MIN_VISIBLE = 24;
  const MAX_VISIBLE = 140;
  const PX_PER_BAR = 14;
  const FUTURE_SPACE = 56;
  const LEFT_AXIS = 12;
  const RIGHT_AXIS_MIN = 62;
  const RIGHT_AXIS_RATIO = 0.075;

  let lastBitmapWidth = 0;
  let lastBitmapHeight = 0;
  let lastDpr = 0;
  let lastCandleCount = 0;

  function getState() {
    return window.WebariaChartState || null;
  }

  function syncCanvasBitmap() {
    const width = Math.max(1, Math.floor(canvas.clientWidth || wrap.clientWidth));
    const height = Math.max(1, Math.floor(canvas.clientHeight || wrap.clientHeight));
    const dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const bitmapWidth = Math.round(width * dpr);
    const bitmapHeight = Math.round(height * dpr);

    if (bitmapWidth === lastBitmapWidth && bitmapHeight === lastBitmapHeight && dpr === lastDpr) return;

    canvas.width = bitmapWidth;
    canvas.height = bitmapHeight;
    lastBitmapWidth = bitmapWidth;
    lastBitmapHeight = bitmapHeight;
    lastDpr = dpr;

    const ctx = canvas.getContext('2d');
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function fitToViewport() {
    const state = getState();
    if (!state || !Array.isArray(state.candles) || !state.candles.length) return;
    if (state._userViewport) return;

    const width = Math.max(1, canvas.clientWidth || wrap.clientWidth);
    const rightAxis = Math.max(RIGHT_AXIS_MIN, Math.min(92, width * RIGHT_AXIS_RATIO));
    const plotWidth = Math.max(1, width - LEFT_AXIS - rightAxis - FUTURE_SPACE);
    const target = Math.round(plotWidth / PX_PER_BAR);
    const visible = Math.max(MIN_VISIBLE, Math.min(MAX_VISIBLE, state.candles.length, target));

    state.visibleBars = visible;
    state.offset = 0;
  }

  const originalDraw = window.draw;
  if (typeof originalDraw !== 'function') return;

  window.draw = function () {
    syncCanvasBitmap();
    const state = getState();
    const candleCount = Array.isArray(state?.candles) ? state.candles.length : 0;
    if (candleCount !== lastCandleCount || !state?._userViewport) {
      fitToViewport();
      lastCandleCount = candleCount;
    }
    return originalDraw.apply(this, arguments);
  };

  function redrawForResize() {
    syncCanvasBitmap();
    const state = getState();
    if (state && !state._userViewport) fitToViewport();
    window.draw();
  }

  const resizeObserver = typeof ResizeObserver === 'function'
    ? new ResizeObserver(redrawForResize)
    : null;
  if (resizeObserver) resizeObserver.observe(wrap);
  window.addEventListener('resize', redrawForResize, { passive: true });

  syncCanvasBitmap();
  fitToViewport();
  window.draw();
})();
