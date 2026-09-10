(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const wrap = document.getElementById('chartwrap');
  const state = window.WebariaChartState;
  if (!canvas || !wrap || !state) return;

  // trading.js is the single source of truth for chart geometry, viewport,
  // zoom, pan, drawing tools, and resize. This module intentionally contains
  // no competing candle/layout math.
  const redraw = () => {
    if (typeof window.draw === 'function') window.draw();
  };

  const resize = () => {
    if (typeof window.resize === 'function') {
      window.resize();
    } else {
      redraw();
    }
  };

  window.WebariaChartUX = Object.freeze({
    fit() {
      if (typeof window.fitVisibleBars === 'function') {
        window.fitVisibleBars();
      } else {
        state._userViewport = false;
        resize();
      }
    },
    resetZoom() {
      this.fit();
    },
    zoomIn() {
      if (typeof window.setZoom === 'function') window.setZoom(state.visibleBars * 0.82);
    },
    zoomOut() {
      if (typeof window.setZoom === 'function') window.setZoom(state.visibleBars * 1.22);
    },
    resize
  });

  // Do not bind wheel/pointer events here. trading.js owns all gestures.
  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  canvas.style.webkitUserSelect = 'none';

  const ro = typeof ResizeObserver === 'function'
    ? new ResizeObserver(() => requestAnimationFrame(resize))
    : null;
  if (ro) ro.observe(wrap);

  window.addEventListener('resize', () => requestAnimationFrame(resize), { passive: true });
})();
