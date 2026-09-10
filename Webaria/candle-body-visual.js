/* Visual-only candle body enhancement.
 * Keeps OHLC/wicks unchanged while making very small candle bodies readable.
 */
(function () {
  'use strict';

  const originalFillRect = CanvasRenderingContext2D.prototype.fillRect;
  const MIN_BODY_HEIGHT = 12;

  CanvasRenderingContext2D.prototype.fillRect = function (x, y, width, height) {
    const isCandleColor = this.fillStyle === '#26a69a' || this.fillStyle === '#ef5350';
    const isCandleBody = isCandleColor && width >= 3 && width <= 24 && height >= 0 && height <= 3;

    if (isCandleBody) {
      const centerY = y + height / 2;
      y = centerY - MIN_BODY_HEIGHT / 2;
      height = MIN_BODY_HEIGHT;
    }

    return originalFillRect.call(this, x, y, width, height);
  };
})();
