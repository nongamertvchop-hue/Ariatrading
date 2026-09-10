import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../Webaria/paper-engine.js', import.meta.url), 'utf8');
const context = { console };
vm.runInNewContext(source, context, { filename: 'paper-engine.js' });
const engine = context.WebariaPaperEngine;

assert.ok(engine, 'WebariaPaperEngine must be exported');

 test('unrealizedPnl rejects an invalid side instead of treating it as LONG', () => {
  assert.throws(
    () => engine.unrealizedPnl({ side: 'INVALID', quantity: 1, entry: 100 }, 101),
    /side must be LONG or SHORT/
  );
});

test('riskReward validates stop and target geometry', () => {
  assert.equal(engine.riskReward(100, 95, 110, engine.LONG), 2);
  assert.throws(
    () => engine.riskReward(100, 105, 110, engine.LONG),
    /stop loss is on the wrong side of entry/
  );
  assert.throws(
    () => engine.riskReward(100, 95, 90, engine.LONG),
    /take profit is on the wrong side of entry/
  );
});

test('barExit remains conservative when both stop and target are inside one bar', () => {
  const result = engine.barExit(
    { side: engine.LONG, entry: 100, sl: 95, tp: 110 },
    { high: 112, low: 94 }
  );
  assert.deepEqual(result, { reason: 'stop loss', price: 95, outcome: 'LOSS' });
});

test('evaluateRisk rejects invalid limit contracts', () => {
  assert.throws(
    () => engine.evaluateRisk({
      equity: 10000,
      entry: 100,
      stop: 95,
      limits: { riskPerTrade: 1.5 }
    }),
    /limits\.riskPerTrade must be > 0 and <= 1/
  );

  assert.throws(
    () => engine.evaluateRisk({
      equity: 10000,
      entry: 100,
      stop: 95,
      limits: { minQuantity: 2, maxQuantity: 1 }
    }),
    /limits\.maxQuantity must be >= limits\.minQuantity/
  );

  assert.throws(
    () => engine.evaluateRisk({
      equity: 10000,
      entry: 100,
      stop: 95,
      openPositions: 0.5
    }),
    /openPositions must be an integer >= 0/
  );
});

test('evaluateRisk preserves deterministic sizing under valid limits', () => {
  const result = engine.evaluateRisk({
    equity: 10000,
    entry: 100,
    stop: 95,
    quantityStep: 0.1,
    valuePerPriceUnit: 1,
    limits: { riskPerTrade: 0.01, maxOpenRisk: 0.02, maxPositions: 1 }
  });

  assert.equal(result.allowed, true);
  assert.equal(result.quantity, 20);
  assert.equal(result.riskAmount, 100);
  assert.equal(result.riskFraction, 0.01);
});
