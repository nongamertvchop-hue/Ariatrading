/* Webaria chart data compatibility layer.
 * Normalizes market timestamps at the API boundary so canvas coordinates,
 * drawings, hover labels, and time-axis rendering all use milliseconds.
 */
(function () {
  'use strict';

  const originalFetch = window.fetch.bind(window);
  const isSignalRequest = (input) => {
    const url = typeof input === 'string' ? input : input?.url;
    return typeof url === 'string' && /\/api\/signal(?:[/?]|$)/.test(url);
  };

  function normalizeTimestamp(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      const absolute = Math.abs(value);
      // Unix seconds are currently ~1e9; Unix milliseconds are ~1e12.
      if (absolute > 0 && absolute < 1e11) return value * 1000;
    }
    if (typeof value === 'string' && /^\d+(?:\.\d+)?$/.test(value.trim())) {
      const numeric = Number(value);
      if (Number.isFinite(numeric) && Math.abs(numeric) < 1e11) return numeric * 1000;
    }
    return value;
  }

  function normalizeChartPayload(payload) {
    if (!payload || !Array.isArray(payload.candles)) return payload;

    return {
      ...payload,
      candles: payload.candles.map((candle) => ({
        ...candle,
        time: normalizeTimestamp(candle?.time ?? candle?.datetime),
      })),
    };
  }

  window.WebariaChartData = Object.freeze({ normalizeTimestamp, normalizeChartPayload });

  window.fetch = async function webariaChartFetch(input, init) {
    const response = await originalFetch(input, init);
    if (!isSignalRequest(input)) return response;

    try {
      const payload = await response.clone().json();
      const normalized = normalizeChartPayload(payload);
      if (normalized === payload) return response;

      const headers = new Headers(response.headers);
      headers.set('content-type', 'application/json; charset=utf-8');
      return new Response(JSON.stringify(normalized), {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    } catch {
      // Never turn a valid API response into a chart failure because the
      // compatibility layer could not parse or reconstruct it.
      return response;
    }
  };
})();
