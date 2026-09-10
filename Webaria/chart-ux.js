(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  // Use a deliberately lower candle count so each candle remains readable.
  // The chart is a price-action terminal, so legibility is more important than
  // showing as much history as possible in the first viewport.
  const MIN_BARS = 20;
  const MAX_BARS = 70;
  const TARGET_PX_PER_BAR = 22;
  const LEFT = 12;
  const MIN_RIGHT_AXIS = 62;

  let userZoomed = false;
  let preferredVisible = null;
  let preferredOffset = null;
  let lastCount = 0;
  let lastWidth = 0;
  let lastHeight = 0;
  let pan = null;
  let wheelFrame = false;

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const count = () => Array.isArray(state.candles) ? state.candles.length : 0;
  const rightAxis = width => Math.max(MIN_RIGHT_AXIS, Math.min(92, width * 0.075));
  const plotWidth = width => Math.max(1, width - LEFT - rightAxis(width));
  const redraw = () => {
    if (typeof window.draw === 'function') window.draw();
    else window.dispatchEvent(new Event('resize'));
  };

  function normalizeViewport() {
    const total = count();
    if (!total) return;
    const maxVisible = Math.min(MAX_BARS, total);
    state.visibleBars = clamp(Math.round(Number(state.visibleBars) || maxVisible), MIN_BARS, maxVisible);
    const maxOffset = Math.max(0, total - state.visibleBars);
    state.offset = clamp(Math.round(Number(state.offset) || 0), 0, maxOffset);
  }

  function fit() {
    const total = count();
    const width = wrap.clientWidth;
    if (!total || width < 1) return;

    const target = Math.round(plotWidth(width) / TARGET_PX_PER_BAR);
    state.visibleBars = clamp(target, MIN_BARS, Math.min(MAX_BARS, total));
    state.offset = 0;
    preferredVisible = state.visibleBars;
    preferredOffset = 0;
    redraw();
  }

  function remember() {
    normalizeViewport();
    preferredVisible = state.visibleBars;
    preferredOffset = state.offset;
  }

  function restore() {
    if (!userZoomed || preferredVisible == null) return false;
    const beforeVisible = state.visibleBars;
    const beforeOffset = state.offset;
    state.visibleBars = preferredVisible;
    state.offset = preferredOffset ?? 0;
    normalizeViewport();
    preferredVisible = state.visibleBars;
    preferredOffset = state.offset;
    return beforeVisible !== state.visibleBars || beforeOffset !== state.offset;
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
      if (context) context.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const changed = Math.abs(width - lastWidth) > 2 || Math.abs(height - lastHeight) > 2;
    if (changed && !userZoomed) fit();
    lastWidth = width;
    lastHeight = height;
    redraw();
  }

  function zoomAt(clientX, factor) {
    const total = count();
    if (!total) return;
    normalizeViewport();
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const x = clamp(clientX - rect.left, 0, width);
    const pw = plotWidth(width);
    const ratio = clamp((x - LEFT) / pw, 0, 1);

    const oldVisible = state.visibleBars;
    const oldOffset = state.offset;
    const oldEnd = total - oldOffset;
    const oldStart = Math.max(0, oldEnd - oldVisible);
    const anchor = oldStart + ratio * Math.max(1, oldVisible - 1);

    const requested = Math.round(oldVisible * factor);
    const newVisible = clamp(requested, MIN_BARS, Math.min(MAX_BARS, total));
    const maxStart = Math.max(0, total - newVisible);
    const newStart = clamp(Math.round(anchor - ratio * Math.max(1, newVisible - 1)), 0, maxStart);

    state.visibleBars = newVisible;
    state.offset = total - (newStart + newVisible);
    userZoomed = true;
    remember();
    redraw();
  }

  function panPixels(dx) {
    const total = count();
    if (!total) return;
    normalizeViewport();
    const barsPerPixel = state.visibleBars / plotWidth(canvas.clientWidth);
    state.offset = clamp(
      Math.round(state.offset + dx * barsPerPixel),
      0,
      Math.max(0, total - state.visibleBars)
    );
    userZoomed = true;
    remember();
    redraw();
  }

  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  canvas.style.webkitUserSelect = 'none';

  canvas.addEventListener('wheel', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (wheelFrame) return;
    wheelFrame = true;
    zoomAt(event.clientX, event.deltaY > 0 ? 1.16 : 0.862);
    requestAnimationFrame(() => { wheelFrame = false; });
  }, {capture: true, passive: false});

  canvas.addEventListener('pointerdown', event => {
    if (state.tool !== 'cursor') return;
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    if (state.pointers && state.pointers.size > 1) return;
    pan = {id: event.pointerId, x: event.clientX};
    try { canvas.setPointerCapture(event.pointerId); } catch {}
  }, {capture: true});

  canvas.addEventListener('pointermove', event => {
    if (!pan || pan.id !== event.pointerId || state.tool !== 'cursor') return;
    const dx = pan.x - event.clientX;
    if (Math.abs(dx) < 1) return;
    pan.x = event.clientX;
    panPixels(dx);
    event.preventDefault();
    event.stopImmediatePropagation();
  }, {capture: true});

  const endPan = event => {
    if (!pan || (event && pan.id !== event.pointerId)) return;
    try { canvas.releasePointerCapture(pan.id); } catch {}
    pan = null;
  };
  canvas.addEventListener('pointerup', endPan, {capture: true});
  canvas.addEventListener('pointercancel', endPan, {capture: true});
  canvas.addEventListener('lostpointercapture', () => { pan = null; }, {capture: true});

  window.WebariaChartUX = {
    fit: () => { userZoomed = false; fit(); },
    resetZoom: () => { userZoomed = false; fit(); },
    zoomIn: () => zoomAt(canvas.getBoundingClientRect().left + canvas.clientWidth / 2, 0.80),
    zoomOut: () => zoomAt(canvas.getBoundingClientRect().left + canvas.clientWidth / 2, 1.25)
  };

  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resizeCanvas) : null;
  if (ro) ro.observe(wrap);
  window.addEventListener('resize', resizeCanvas, {passive: true});

  // trading.js still resets to 90 bars during refresh. Detect that specific
  // reset and immediately re-fit instead of allowing the chart to remain
  // compressed. User zoom/pan is always restored and is never overridden.
  setInterval(() => {
    const total = count();
    if (!total) return;

    if (userZoomed) {
      restore();
      return;
    }

    const width = wrap.clientWidth;
    const target = clamp(Math.round(plotWidth(width) / TARGET_PX_PER_BAR), MIN_BARS, Math.min(MAX_BARS, total));
    if (state.visibleBars !== target || state.offset !== 0 || total !== lastCount) {
      state.visibleBars = target;
      state.offset = 0;
      preferredVisible = target;
      preferredOffset = 0;
      lastCount = total;
      redraw();
    }
  }, 50);

  setTimeout(() => {
    resizeCanvas();
    if (count() && !userZoomed) fit();
  }, 0);
})();
