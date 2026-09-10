/* Webaria browser bootstrap: keeps the canvas lifecycle explicit and fail-safe. */
(function (root) {
  'use strict';

  root.resize = function resizeCanvas() {
    const canvas = document.getElementById('chart');
    const wrap = document.getElementById('chartwrap');
    if (!canvas || !wrap) return;

    const rect = wrap.getBoundingClientRect();
    const dpr = Math.max(1, Math.min(2, Number(root.devicePixelRatio) || 1));
    const width = Math.max(1, Math.floor(rect.width * dpr));
    const height = Math.max(1, Math.floor(rect.height * dpr));

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      canvas.style.width = `${Math.max(1, Math.floor(rect.width))}px`;
      canvas.style.height = `${Math.max(1, Math.floor(rect.height))}px`;
      const context = canvas.getContext('2d');
      if (context) context.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    if (typeof root.draw === 'function') root.draw();
  };
})(window);
