import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync('Webaria/chart-data-compat.js', 'utf8');
const context = {
  window: { fetch() {} },
  Headers,
  Response,
};
vm.runInNewContext(source, context);

const { normalizeTimestamp, normalizeChartPayload } = context.window.WebariaChartData;

test('normalizes Unix seconds to milliseconds', () => {
  assert.equal(normalizeTimestamp(1725000000), 1725000000000);
});

test('keeps Unix milliseconds unchanged', () => {
  assert.equal(normalizeTimestamp(1725000000000), 1725000000000);
});

test('normalizes numeric timestamp strings', () => {
  assert.equal(normalizeTimestamp('1725000000'), 1725000000000);
});

test('keeps ISO timestamps unchanged', () => {
  const value = '2026-09-10T08:00:00Z';
  assert.equal(normalizeTimestamp(value), value);
});

test('normalizes candle time without changing OHLC values', () => {
  const payload = {
    symbol: 'EUR/USD',
    candles: [
      { time: 1725000000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
    ],
  };
  const result = normalizeChartPayload(payload);
  assert.equal(result.symbol, 'EUR/USD');
  assert.equal(result.candles.length, 1);
  assert.deepEqual({ ...result.candles[0] }, {
    time: 1725000000000,
    open: 1.1,
    high: 1.2,
    low: 1.0,
    close: 1.15,
  });
});
