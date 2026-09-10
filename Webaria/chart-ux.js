(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  // chart-ux owns viewport sizing and high-level controls only. trading.js is
  // the single owner of zoom, pan, pointer and drawing interactions.
  const MIN_BARS = 16;
  const MAX_BARS = 110;
  const TARGET_PX_PER_BAR = 15;
  const LEFT = 12;
  const MIN_RIGHT_AXIS = 62;

  let lastWidth = 0;
  let lastHeight = 0;
  let scheduled = false;

  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const count = () => Array.isArray(state.candles) ? state.candles.length : 0;
  const rightAxis = width => Math.max(MIN_RIGHT_AXIS, Math.min(92, width * 0.075));
  const plotWidth = width => Math.max(1, width - LEFT - rightAxis(width));
  const redraw = () => {
    if (typeof window.draw === 'function') window.draw();
  };

  function fit(markUserAction = true) {
    const total = count();
    const width = wrap.clientWidth;
    if (!total || width < 1) return;

    const target = Math.round(plotWidth(width) / TARGET_PX_PER_BAR);
    state.visibleBars = clamp(target, MIN_BARS, Math.min(MAX_BARS, total));
    state.offset = 0;
    if (markUserAction) state._userViewport = false;
    redraw();
  }

  function normalizeViewport() {
    const total = count();
    if (!total) return;
    const maxVisible = Math.min(MAX_BARS, total);
    state.visibleBars = clamp(Math.round(Number(state.visibleBars) || maxVisible), MIN_BARS, maxVisible);
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

    // A resize should re-fit only while the user is using the automatic
    // viewport. Manual zoom/pan must survive orientation changes and panels.
    if (changed && !state.dragging && !state.draft && !state._userViewport) {
      fit(false);
    }
    redraw();
  }

  // Preserve the user's viewport across trading.js data reloads. This removes
  // the old visible "jump back to 90 bars" during Refresh and the 30s poll.
  const originalLoad = window.load;
  if (typeof originalLoad === 'function') {
    window.load = async function wrappedLoad(...args) {
      const beforeKey = `${state.symbol}|${state.tf}`;
      const hadCandles = count() > 0;
      const beforeVisible = state.visibleBars;
      const beforeOffset = state.offset;
      const result = await originalLoad.apply(this, args);
      const afterKey = `${state.symbol}|${state.tf}`;

      if (hadCandles && beforeKey === afterKey && count() > 0) {
        state.visibleBars = beforeVisible;
        state.offset = beforeOffset;
        normalizeViewport();
        state._userViewport = true;
      } else if (!state._userViewport) {
        fit(false);
      }
      redraw();
      return result;
    };
  }

  // Mark a viewport as user-controlled only after trading.js has processed the
  // gesture. No competing gesture implementation lives here.
  const markViewportFromUser = () => {
    if (count()) state._userViewport = true;
  };
  canvas.addEventListener('pointerup', markViewportFromUser, {passive: true});
  canvas.addEventListener('wheel', markViewportFromUser, {passive: true});
  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  canvas.style.webkitUserSelect = 'none';

  window.WebariaChartUX = {
    fit: () => { state._userViewport = false; fit(true); },
    resetZoom: () => { state._userViewport = false; fit(true); },
    zoomIn: () => {
      if (typeof window.setZoom === 'function') {
        window.setZoom(state.visibleBars * 0.82);
        state._userViewport = true;
      }
    },
    zoomOut: () => {
      if (typeof window.setZoom === 'function') {
        window.setZoom(state.visibleBars * 1.22);
        state._userViewport = true;
      }
    },
    resize: resizeCanvas
  };

  const fitButton = document.getElementById('fit');
  if (fitButton) fitButton.onclick = () => window.WebariaChartUX.fit();

  const resetButton = document.getElementById('reset');
  if (resetButton) resetButton.onclick = () => {
    state.selectedDrawing = null;
    state._userViewport = false;
    window.WebariaChartUX.fit();
  };

  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      resizeCanvas();
    });
  }) : null;
  if (ro) ro.observe(wrap);

  window.addEventListener('resize', () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      resizeCanvas();
    });
  }, {passive: true});

  setTimeout(resizeCanvas, 0);
})();
