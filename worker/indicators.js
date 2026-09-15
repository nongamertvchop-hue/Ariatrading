/**
 * Deterministic causal indicators for the Worker runtime.
 *
 * Values are calculated from chronological closed OHLC candles only. The
 * indicator layer is context/evidence; it never creates a trading action.
 */

function finite(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${name} must be finite`);
  return number;
}

function closes(candles) {
  return candles.map((candle) => finite(candle.close, "close"));
}

function validatePeriod(period) {
  if (!Number.isInteger(period) || period < 1) throw new Error("period must be >= 1");
}

export function emaSeries(candles, period) {
  validatePeriod(period);
  const values = closes(candles);
  const result = Array(values.length).fill(null);
  if (values.length < period) return result;
  let current = values.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period - 1] = current;
  const alpha = 2 / (period + 1);
  for (let index = period; index < values.length; index += 1) {
    current = (values[index] - current) * alpha + current;
    result[index] = current;
  }
  return result;
}

export function rsiSeries(candles, period = 14) {
  validatePeriod(period);
  const values = closes(candles);
  const result = Array(values.length).fill(null);
  if (values.length <= period) return result;

  const gains = [];
  const losses = [];
  for (let index = 1; index < values.length; index += 1) {
    const change = values[index] - values[index - 1];
    gains.push(Math.max(change, 0));
    losses.push(Math.max(-change, 0));
  }
  let averageGain = gains.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  let averageLoss = losses.slice(0, period).reduce((sum, value) => sum + value, 0) / period;

  const toRsi = (gain, loss) => {
    if (loss === 0) return gain > 0 ? 100 : 50;
    if (gain === 0) return 0;
    return 100 - (100 / (1 + gain / loss));
  };

  result[period] = toRsi(averageGain, averageLoss);
  for (let index = period + 1; index < values.length; index += 1) {
    averageGain = ((averageGain * (period - 1)) + gains[index - 1]) / period;
    averageLoss = ((averageLoss * (period - 1)) + losses[index - 1]) / period;
    result[index] = toRsi(averageGain, averageLoss);
  }
  return result;
}

export function trueRangeSeries(candles) {
  if (!candles.length) return [];
  const result = [];
  let previousClose = null;
  for (const candle of candles) {
    const high = finite(candle.high, "high");
    const low = finite(candle.low, "low");
    if (high < low) throw new Error("high must be >= low");
    const currentClose = finite(candle.close, "close");
    result.push(previousClose === null
      ? high - low
      : Math.max(high - low, Math.abs(high - previousClose), Math.abs(low - previousClose)));
    previousClose = currentClose;
  }
  return result;
}

export function atrSeries(candles, period = 14) {
  validatePeriod(period);
  const ranges = trueRangeSeries(candles);
  const result = Array(ranges.length).fill(null);
  if (ranges.length < period) return result;
  let current = ranges.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period - 1] = current;
  for (let index = period; index < ranges.length; index += 1) {
    current = ((current * (period - 1)) + ranges[index]) / period;
    result[index] = current;
  }
  return result;
}

function wilderSmooth(values, period) {
  validatePeriod(period);
  const result = Array(values.length).fill(null);
  if (values.length < period) return result;
  let current = values.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period - 1] = current;
  for (let index = period; index < values.length; index += 1) {
    current = ((current * (period - 1)) + values[index]) / period;
    result[index] = current;
  }
  return result;
}

export function adxSeries(candles, period = 14) {
  validatePeriod(period);
  if (!candles.length) return [];
  const highs = candles.map((candle) => finite(candle.high, "high"));
  const lows = candles.map((candle) => finite(candle.low, "low"));
  if (candles.length < period * 2) return Array(candles.length).fill(null);

  const tr = trueRangeSeries(candles);
  const plusDm = [0];
  const minusDm = [0];
  for (let index = 1; index < candles.length; index += 1) {
    const up = highs[index] - highs[index - 1];
    const down = lows[index - 1] - lows[index];
    plusDm.push(up > down && up > 0 ? up : 0);
    minusDm.push(down > up && down > 0 ? down : 0);
  }

  const smoothedTr = wilderSmooth(tr, period);
  const smoothedPlus = wilderSmooth(plusDm, period);
  const smoothedMinus = wilderSmooth(minusDm, period);
  const dx = Array(candles.length).fill(null);
  for (let index = 0; index < candles.length; index += 1) {
    const trValue = smoothedTr[index];
    const plusValue = smoothedPlus[index];
    const minusValue = smoothedMinus[index];
    if (trValue === null || plusValue === null || minusValue === null || trValue === 0) continue;
    const plusDi = 100 * plusValue / trValue;
    const minusDi = 100 * minusValue / trValue;
    const denominator = plusDi + minusDi;
    dx[index] = denominator === 0 ? 0 : 100 * Math.abs(plusDi - minusDi) / denominator;
  }

  const firstDxIndex = dx.findIndex((value) => value !== null);
  const result = Array(candles.length).fill(null);
  if (firstDxIndex < 0 || dx.slice(firstDxIndex).filter((value) => value !== null).length < period) return result;
  const seedEnd = firstDxIndex + period;
  const seed = dx.slice(firstDxIndex, seedEnd).filter((value) => value !== null);
  if (seed.length < period) return result;
  let current = seed.reduce((sum, value) => sum + value, 0) / period;
  result[seedEnd - 1] = current;
  for (let index = seedEnd; index < candles.length; index += 1) {
    if (dx[index] === null) continue;
    current = ((current * (period - 1)) + dx[index]) / period;
    result[index] = current;
  }
  return result;
}

export function macdSeries(candles, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
  if (fastPeriod >= slowPeriod) throw new Error("fastPeriod must be < slowPeriod");
  validatePeriod(fastPeriod);
  validatePeriod(slowPeriod);
  validatePeriod(signalPeriod);
  const fast = emaSeries(candles, fastPeriod);
  const slow = emaSeries(candles, slowPeriod);
  const line = Array(candles.length).fill(null);
  const compact = [];
  const indices = [];
  for (let index = 0; index < candles.length; index += 1) {
    if (fast[index] === null || slow[index] === null) continue;
    const value = fast[index] - slow[index];
    line[index] = value;
    compact.push(value);
    indices.push(index);
  }

  const signalCompact = Array(compact.length).fill(null);
  if (compact.length >= signalPeriod) {
    let current = compact.slice(0, signalPeriod).reduce((sum, value) => sum + value, 0) / signalPeriod;
    signalCompact[signalPeriod - 1] = current;
    const alpha = 2 / (signalPeriod + 1);
    for (let index = signalPeriod; index < compact.length; index += 1) {
      current = (compact[index] - current) * alpha + current;
      signalCompact[index] = current;
    }
  }

  const signal = Array(candles.length).fill(null);
  const histogram = Array(candles.length).fill(null);
  for (let index = 0; index < indices.length; index += 1) {
    const candleIndex = indices[index];
    signal[candleIndex] = signalCompact[index];
    if (signalCompact[index] !== null) histogram[candleIndex] = line[candleIndex] - signalCompact[index];
  }
  return { line, signal, histogram };
}

export function calculateIndicators(candles) {
  const macdValues = macdSeries(candles);
  const ema20 = emaSeries(candles, 20);
  const ema50 = emaSeries(candles, 50);
  const ema200 = emaSeries(candles, 200);
  const rsi14 = rsiSeries(candles, 14);
  const atr14 = atrSeries(candles, 14);
  const adx14 = adxSeries(candles, 14);
  const last = candles.length - 1;
  return {
    ema20: last >= 0 ? ema20[last] : null,
    ema50: last >= 0 ? ema50[last] : null,
    ema200: last >= 0 ? ema200[last] : null,
    rsi14: last >= 0 ? rsi14[last] : null,
    atr14: last >= 0 ? atr14[last] : null,
    adx14: last >= 0 ? adx14[last] : null,
    macd: last >= 0 ? macdValues.line[last] : null,
    macd_signal: last >= 0 ? macdValues.signal[last] : null,
    macd_histogram: last >= 0 ? macdValues.histogram[last] : null,
  };
}

export function indicatorContext(candles, direction) {
  const values = calculateIndicators(candles);
  const trendReady = values.ema20 !== null && values.ema50 !== null;
  const trend = !trendReady ? "UNAVAILABLE" : values.ema20 > values.ema50 ? "BULLISH" : values.ema20 < values.ema50 ? "BEARISH" : "NEUTRAL";
  const momentum = values.rsi14 === null ? "UNAVAILABLE" : values.rsi14 > 50 ? "BULLISH" : values.rsi14 < 50 ? "BEARISH" : "NEUTRAL";
  const macdMomentum = values.macd === null || values.macd_signal === null ? "UNAVAILABLE" : values.macd > values.macd_signal ? "BULLISH" : values.macd < values.macd_signal ? "BEARISH" : "NEUTRAL";
  const strength = values.adx14 === null ? "UNAVAILABLE" : values.adx14 >= 25 ? "TRENDING" : "RANGING";
  const directionMatches = (bias) => direction === "LONG" ? bias === "BULLISH" : direction === "SHORT" ? bias === "BEARISH" : false;
  const confirmations = [trend, momentum, macdMomentum].filter((bias) => directionMatches(bias)).length;
  return {
    values,
    trend,
    momentum,
    macd_momentum: macdMomentum,
    trend_strength: strength,
    direction: direction ?? null,
    confirmations,
    confirmation_state: direction ? (confirmations >= 2 ? "SUPPORTIVE" : confirmations === 1 ? "MIXED" : "OPPOSED") : "NEUTRAL",
  };
}
