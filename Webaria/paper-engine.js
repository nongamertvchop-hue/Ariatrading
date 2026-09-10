/*
 * Webaria Paper Engine
 *
 * Browser-safe risk primitives mirroring strategy/risk_engine.py.
 * This module is intentionally simulation-only: it never calls a broker.
 *
 * The public functions validate their contracts aggressively so malformed UI
 * state cannot silently turn into a plausible-looking paper calculation.
 */
(function (root) {
  'use strict';

  const LONG = 'LONG';
  const SHORT = 'SHORT';
  const EPSILON = 1e-12;

  function finitePositive(value, name) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) throw new Error(name + ' must be finite and > 0');
    return n;
  }

  function finiteNonNegative(value, name) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0) throw new Error(name + ' must be finite and >= 0');
    return n;
  }

  function fraction(value, name) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0 || n > 1) throw new Error(name + ' must be > 0 and <= 1');
    return n;
  }

  function integerNonNegative(value, name) {
    const n = Number(value);
    if (!Number.isInteger(n) || n < 0) throw new Error(name + ' must be an integer >= 0');
    return n;
  }

  function floorStep(value, step) {
    if (!Number.isFinite(step) || step < 0) throw new Error('quantityStep must be finite and >= 0');
    if (step === 0) return value;
    const units = Math.floor((value + EPSILON) / step);
    return units * step;
  }

  function validateStops(side, price, sl, tp) {
    if (side !== LONG && side !== SHORT) throw new Error('side must be LONG or SHORT');
    const entry = finitePositive(price, 'price');
    const stop = sl == null || sl === '' ? null : Number(sl);
    const target = tp == null || tp === '' ? null : Number(tp);

    if (stop !== null && (!Number.isFinite(stop) || stop <= 0)) throw new Error('stop loss must be finite and > 0');
    if (target !== null && (!Number.isFinite(target) || target <= 0)) throw new Error('take profit must be finite and > 0');

    if (stop !== null && ((side === LONG && stop >= entry) || (side === SHORT && stop <= entry))) {
      throw new Error('stop loss is on the wrong side of entry');
    }
    if (target !== null && ((side === LONG && target <= entry) || (side === SHORT && target >= entry))) {
      throw new Error('take profit is on the wrong side of entry');
    }

    return { entry, stop, target };
  }

  function positionSize(equity, entry, stop, riskFraction, options) {
    const cfg = options || {};
    const eq = finitePositive(equity, 'equity');
    const en = finitePositive(entry, 'entry');
    const st = finitePositive(stop, 'stop');
    const rf = fraction(riskFraction, 'riskFraction');
    const valuePerPriceUnit = cfg.valuePerPriceUnit == null ? 1 : Number(cfg.valuePerPriceUnit);
    const quantityStep = cfg.quantityStep == null ? 0 : Number(cfg.quantityStep);
    if (!Number.isFinite(valuePerPriceUnit) || valuePerPriceUnit <= 0) throw new Error('valuePerPriceUnit must be finite and > 0');
    if (!Number.isFinite(quantityStep) || quantityStep < 0) throw new Error('quantityStep must be finite and >= 0');
    if (en === st) throw new Error('entry and stop must differ');
    const riskBudget = eq * rf;
    const riskPerUnit = Math.abs(en - st) * valuePerPriceUnit;
    return floorStep(riskBudget / riskPerUnit, quantityStep);
  }

  function validateLimits(raw) {
    const limits = Object.assign({
      riskPerTrade: 0.01,
      maxDailyLoss: 0.03,
      maxOpenRisk: 0.02,
      maxPositions: 1,
      minQuantity: 0,
      maxQuantity: null
    }, raw || {});

    fraction(limits.riskPerTrade, 'limits.riskPerTrade');
    fraction(limits.maxDailyLoss, 'limits.maxDailyLoss');
    fraction(limits.maxOpenRisk, 'limits.maxOpenRisk');
    integerNonNegative(limits.maxPositions, 'limits.maxPositions');
    finiteNonNegative(limits.minQuantity, 'limits.minQuantity');

    if (limits.maxQuantity != null) {
      finiteNonNegative(limits.maxQuantity, 'limits.maxQuantity');
      if (limits.maxQuantity < limits.minQuantity) {
        throw new Error('limits.maxQuantity must be >= limits.minQuantity');
      }
    }

    return limits;
  }

  function evaluateRisk(params) {
    const p = params || {};
    const equity = finitePositive(p.equity, 'equity');
    const entry = finitePositive(p.entry, 'entry');
    const stop = finitePositive(p.stop, 'stop');
    const limits = validateLimits(p.limits);
    const dailyLoss = Number(p.dailyRealizedLoss || 0);
    const openRisk = Number(p.openRiskAmount || 0);
    const openPositions = Number(p.openPositions || 0);
    if (![dailyLoss, openRisk, openPositions].every(Number.isFinite)) throw new Error('risk state must be finite');
    if (dailyLoss < 0 || openRisk < 0 || openPositions < 0) throw new Error('risk state cannot be negative');
    if (!Number.isInteger(openPositions)) throw new Error('openPositions must be an integer >= 0');

    if (dailyLoss >= equity * limits.maxDailyLoss) return { allowed: false, reason: 'daily loss limit reached', quantity: 0, riskAmount: 0, riskFraction: 0 };
    if (openPositions >= limits.maxPositions) return { allowed: false, reason: 'maximum open positions reached', quantity: 0, riskAmount: 0, riskFraction: 0 };

    const remaining = equity * limits.maxOpenRisk - openRisk;
    if (remaining <= 0) return { allowed: false, reason: 'maximum open risk reached', quantity: 0, riskAmount: 0, riskFraction: 0 };

    const requested = Math.min(equity * limits.riskPerTrade, remaining);
    const requestedFraction = requested / equity;
    let quantity = positionSize(equity, entry, stop, requestedFraction, {
      valuePerPriceUnit: p.valuePerPriceUnit == null ? 1 : p.valuePerPriceUnit,
      quantityStep: p.quantityStep == null ? 0 : p.quantityStep
    });

    if (quantity <= 0) return { allowed: false, reason: 'computed quantity is below broker minimum step', quantity: 0, riskAmount: 0, riskFraction: 0 };
    if (limits.minQuantity > 0 && quantity < limits.minQuantity) return { allowed: false, reason: 'computed quantity is below configured minimum quantity', quantity: 0, riskAmount: 0, riskFraction: 0 };

    if (limits.maxQuantity != null) {
      quantity = Math.min(quantity, limits.maxQuantity);
      quantity = floorStep(quantity, p.quantityStep == null ? 0 : Number(p.quantityStep));
      if (quantity <= 0) return { allowed: false, reason: 'maximum quantity cap is below broker minimum step', quantity: 0, riskAmount: 0, riskFraction: 0 };
      if (limits.minQuantity > 0 && quantity < limits.minQuantity) return { allowed: false, reason: 'quantity cap leaves less than configured minimum quantity', quantity: 0, riskAmount: 0, riskFraction: 0 };
    }

    const valuePerPriceUnit = p.valuePerPriceUnit == null ? 1 : Number(p.valuePerPriceUnit);
    if (!Number.isFinite(valuePerPriceUnit) || valuePerPriceUnit <= 0) throw new Error('valuePerPriceUnit must be finite and > 0');
    const riskAmount = Math.abs(entry - stop) * valuePerPriceUnit * quantity;
    if (riskAmount > requested * (1 + EPSILON)) return { allowed: false, reason: 'sizing exceeded the configured risk budget', quantity: 0, riskAmount: 0, riskFraction: 0 };
    return { allowed: true, reason: 'risk checks passed', quantity, riskAmount, riskFraction: riskAmount / equity };
  }

  function unrealizedPnl(position, marketPrice) {
    if (!position) return 0;
    if (position.side !== LONG && position.side !== SHORT) throw new Error('side must be LONG or SHORT');
    const price = finitePositive(marketPrice, 'marketPrice');
    const qty = finitePositive(position.quantity, 'quantity');
    const entry = finitePositive(position.entry, 'entry');
    return (price - entry) * (position.side === LONG ? 1 : -1) * qty;
  }

  function barExit(position, bar) {
    if (!position || typeof position !== 'object') return null;
    if (position.side !== LONG && position.side !== SHORT) throw new Error('side must be LONG or SHORT');
    const high = Number(bar && bar.high);
    const low = Number(bar && bar.low);
    if (!Number.isFinite(high) || !Number.isFinite(low) || high < low) throw new Error('bar high/low must be finite and high >= low');
    const { entry, stop, target } = validateStops(position.side, position.entry, position.sl, position.tp);
    if (position.side === LONG) {
      if (stop !== null && low <= stop) return { reason: 'stop loss', price: stop, outcome: 'LOSS' };
      if (target !== null && high >= target) return { reason: 'take profit', price: target, outcome: 'WIN' };
    } else {
      if (stop !== null && high >= stop) return { reason: 'stop loss', price: stop, outcome: 'LOSS' };
      if (target !== null && low <= target) return { reason: 'take profit', price: target, outcome: 'WIN' };
    }
    void entry;
    return null;
  }

  function riskReward(entry, stop, target, side) {
    const { entry: e, stop: s, target: t } = validateStops(side, entry, stop, target);
    const risk = Math.abs(e - s);
    const reward = Math.abs(t - e);
    if (risk === 0) throw new Error('risk distance must be > 0');
    return reward / risk;
  }

  root.WebariaPaperEngine = Object.freeze({
    LONG,
    SHORT,
    validateStops,
    positionSize,
    evaluateRisk,
    unrealizedPnl,
    barExit,
    riskReward
  });
})(typeof window !== 'undefined' ? window : globalThis);
