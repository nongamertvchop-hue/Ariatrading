(() => {
  'use strict';

  const canvas = document.getElementById('chart');
  const state = window.WebariaChartState;
  if (!canvas || !state) return;

  // trading.js owns all chart geometry, viewport math, gestures and resize.
  // This module only exposes a small control surface for other UI modules.
  const click = id => document.getElementById(id)?.click();

  window.WebariaChartUX = Object.freeze({
    fit: () => click('fit'),
    resetZoom: () => click('reset'),
    zoomIn: () => {
      if (typeof window.setZoom === 'function') window.setZoom(state.visibleBars * 0.82);
    },
    zoomOut: () => {
      if (typeof window.setZoom === 'function') window.setZoom(state.visibleBars * 1.22);
    },
    resize: () => {
      if (typeof window.resize === 'function') window.resize();
    }
  });

  canvas.style.touchAction = 'none';
  canvas.style.userSelect = 'none';
  canvas.style.webkitUserSelect = 'none';
})();
