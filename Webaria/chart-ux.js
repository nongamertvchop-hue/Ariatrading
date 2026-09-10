(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  const MIN_BARS = 20;
  const MAX_BARS = 120;
  const TARGET_PX_PER_BAR = 10.5;
  const PLOT_LEFT = 12;

  let userZoomed = false;
  let lastCandleCount = -1;
  let lastWidth = 0;
  let lastHeight = 0;
  let wheelBusy = false;

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const totalBars = () => Array.isArray(state.candles) ? state.candles.length : 0;
  const redraw = () => {
    if (typeof window.draw === 'function') window.draw();
  };

  function fitBarsToWidth() {
    const count = totalBars();
    const width = wrap.clientWidth;
    if (!count || !width) return;

    const rightAxis = Math.max(62, Math.min(92, width * 0.075));
    const usable = Math.max(180, width - PLOT_LEFT - rightAxis);
    const target = clamp(Math.round(usable / TARGET_PX_PER_BAR), MIN_BARS, MAX_BARS);

    state.visibleBars = Math.min(count, target);
    state.offset = 0;
  }

  function clampViewport() {
    const count = totalBars();
    if (!count) return;

    const visible = clamp(Math.round(Number(state.visibleBars) || MIN_BARS), MIN_BARS, Math.min(MAX_BARS, count));
    state.visibleBars = visible;
    const maxOffset = Math.max(0, count - visible);
    state.offset = clamp(Math.round(Number(state.offset) || 0), 0, maxOffset);
  }

  function resizeCanvas() {
    const rect = wrap.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(1, Math.floor(rect.height));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const context = canvas.getContext('2d');
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const resizedMeaningfully = Math.abs(width - lastWidth) > 4 || Math.abs(height - lastHeight) > 4;
    if (!userZoomed && resizedMeaningfully) fitBarsToWidth();

    lastWidth = width;
    lastHeight = height;
    redraw();
  }

  function zoomAt(clientX, factor) {
    const total = totalBars();
    if (!total) return;

    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const x = clamp(clientX - rect.left, 0, width);
    const rightAxis = Math.max(62, Math.min(92, width * 0.075));
    const plotWidth = Math.max(1, width - PLOT_LEFT - rightAxis);
    const ratio = clamp((x - PLOT_LEFT) / plotWidth, 0, 1);

    const oldCount = clamp(Math.round(Number(state.visibleBars) || MIN_BARS), 1, total);
    const oldOffset = clamp(Math.round(Number(state.offset) || 0), 0, Math.max(0, total - oldCount));
    const oldEnd = total - oldOffset;
    const oldStart = Math.max(0, oldEnd - oldCount);
    const anchor = oldStart + ratio * oldCount;

    const requested = Math.round(oldCount * factor);
    const newCount = clamp(requested, MIN_BARS, Math.min(MAX_BARS, total));
    const maxStart = Math.max(0, total - newCount);
    const newStart = clamp(Math.round(anchor - ratio * newCount), 0, maxStart);

    state.visibleBars = newCount;
    state.offset = total - (newStart + newCount);
    clampViewport();
    userZoomed = true;
    redraw();
  }

  function panByPixels(dx) {
    const total = totalBars();
    if (!total) return;

    const visible = clamp(Math.round(Number(state.visibleBars) || MIN_BARS), 1, total);
    const plotWidth = Math.max(1, canvas.clientWidth - PLOT_LEFT - Math.max(62, Math.min(92, canvas.clientWidth * 0.075)));
    const barsPerPixel = visible / plotWidth;
    state.offset = clamp(Math.round((Number(state.offset) || 0) + dx * barsPerPixel), 0, Math.max(0, total - visible));
    userZoomed = true;
    redraw();
  }

  // Own the wheel gesture in capture phase so the older chart handler cannot fight it.
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (wheelBusy) return;
    wheelBusy = true;
    zoomAt(event.clientX, event.deltaY > 0 ? 1.18 : 0.847);
    requestAnimationFrame(() => { wheelBusy = false; });
  }, { passive: false, capture: true });

  // Desktop drag-to-pan. Existing drawing tools still work when another tool is selected.
  let pan = null;
  canvas.addEventListener('pointerdown', (event) => {
    if (state.tool !== 'cursor' || state.pointers?.size > 1) return;
    pan = { x: event.clientX, moved: false };
    canvas.setPointerCapture?.(event.pointerId);
  }, { capture: true });

  canvas.addEventListener('pointermove', (event) => {
    if (!pan || state.tool !== 'cursor' || (state.draft != null)) return;
    const dx = pan.x - event.clientX;
    if (Math.abs(dx) < 2) return;
    pan.moved = true;
    pan.x = event.clientX;
    panByPixels(dx);
    event.stopImmediatePropagation();
  }, { capture: true });

  const endPan = () => { pan = null; };
  canvas.addEventListener('pointerup', endPan, { capture: true });
  canvas.addEventListener('pointercancel', endPan, { capture: true });

  const ro = new ResizeObserver(resizeCanvas);
  ro.observe(wrap);
  window.addEventListener('resize', resizeCanvas, { passive: true });

  window.WebariaChartUX = {
    fit: () => {
      userZoomed = false;
      fitBarsToWidth();
      redraw();
    },
    resetZoom: () => {
      userZoomed = false;
      fitBarsToWidth();
      redraw();
    },
    zoomIn: () => zoomAt(canvas.clientWidth / 2, 0.82),
    zoomOut: () => zoomAt(canvas.clientWidth / 2, 1.22)
  };

  // trading.js refreshes the candles periodically. The old implementation reset the
  // viewport to 90 bars on every refresh. Do not let that destroy the user's view.
  setInterval(() => {
    const count = totalBars();
    if (!count) return;

    if (count !== lastCandleCount) {
      lastCandleCount = count;
      if (!userZoomed) fitBarsToWidth();
      else clampViewport();
      redraw();
      return;
    }

    if (!userZoomed) {
      // Initial data arrival and symbol/timeframe changes can happen without a resize.
      // Always keep the automatic viewport sized to the actual chart width.
      const width = wrap.clientWidth;
      if (width && Math.abs(width - lastWidth) > 1) {
        fitBarsToWidth();
        lastWidth = width;
        redraw();
      }
      return;
    }

    clampViewport();
    redraw();
  }, 250);

  setTimeout(() => {
    resizeCanvas();
    if (!userZoomed && totalBars()) fitBarsToWidth();
    redraw();
  }, 0);
})();
