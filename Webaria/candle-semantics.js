/*
 * ARIA Candlestick Semantics
 *
 * Single source of truth for standard candlestick direction/presentation.
 * Reference: Wikipedia, "Candlestick chart".
 *
 * IMPORTANT:
 * - Green/red is chart presentation, not an order command.
 * - Strategy decisions must still use structure, zones, breakout state,
 *   confirmation and the existing ARIA strategy gates.
 */
(() => {
  const GREEN = '#26a69a';
  const RED = '#ef5350';

  function classify(candle) {
    const open = Number(candle?.open);
    const high = Number(candle?.high);
    const low = Number(candle?.low);
    const close = Number(candle?.close);

    if (![open, high, low, close].every(Number.isFinite)) {
      return { valid: false, direction: 'INVALID', color: null, bias: 'WAIT' };
    }

    // Standard OHLC invariant. Reject malformed candles instead of silently
    // assigning a bullish/bearish meaning to impossible market data.
    if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) {
      return { valid: false, direction: 'INVALID', color: null, bias: 'WAIT' };
    }

    if (close > open) {
      return { valid: true, direction: 'BULLISH', color: GREEN, bias: 'BUY_BIAS' };
    }
    if (close < open) {
      return { valid: true, direction: 'BEARISH', color: RED, bias: 'SELL_BIAS' };
    }

    // Doji/open == close: keep the existing Webaria visual convention green
    // for compatibility, but do NOT treat it as bullish strategy evidence.
    return { valid: true, direction: 'DOJI', color: GREEN, bias: 'WAIT' };
  }

  window.WebariaCandleSemantics = Object.freeze({
    GREEN,
    RED,
    classify,
    isTradeSignalColor: () => false
  });
})();
