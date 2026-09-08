/**
 * Deterministic forecast + realtime supervisor parity helpers.
 *
 * Mirrors strategy/forecast.py and strategy/realtime_supervisor.py.
 * Forecast is context only; it never creates a LONG/SHORT setup.
 */

export const UP = "UP";
export const DOWN = "DOWN";
export const FLAT = "FLAT";
export const ALLOW = "ALLOW";

function mean(values) {
  if (!values.length) throw new Error("mean requires at least one value");
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function validateCandles(candles) {
  if (!candles.length) throw new Error("candles must not be empty");
  for (const candle of candles) {
    for (const key of ["open", "high", "low", "close"]) {
      if (!(key in candle) || !Number.isFinite(Number(candle[key]))) {
        throw new Error(`invalid candle field: ${key}`);
      }
    }
  }
}

function returnsOf(candles) {
  const values = [];
  for (let i = 1; i < candles.length; i += 1) {
    const previous = Number(candles[i - 1].close);
    if (previous !== 0) values.push(Number(candles[i].close) / previous - 1);
  }
  return values;
}

function empiricalDirection(returns, horizon) {
  if (returns.length < horizon + 4) return [1 / 3, 1 / 3, 1 / 3, 0];
  const samples = [];
  for (let origin = 0; origin < returns.length - horizon; origin += 1) {
    samples.push(returns.slice(origin, origin + horizon).reduce((sum, value) => sum + value, 0));
  }
  if (!samples.length) return [1 / 3, 1 / 3, 1 / 3, 0];
  const scale = Math.max(mean(samples.map((value) => Math.abs(value))), 1e-9);
  const threshold = scale * 0.35;
  let up = 0;
  let down = 0;
  for (const value of samples) {
    if (value > threshold) up += 1;
    else if (value < -threshold) down += 1;
  }
  const flat = samples.length - up - down;
  const total = samples.length;
  return [up / total, flat / total, down / total, mean(samples)];
}

function trendBias(returns) {
  const recent = returns.slice(-8);
  if (!recent.length) return 0;
  let numerator = 0;
  let denominator = 0;
  for (let i = 0; i < recent.length; i += 1) {
    const weight = i + 1;
    numerator += recent[i] * weight;
    denominator += weight;
  }
  return Math.max(-1, Math.min(1, numerator / Math.max(denominator, 1)));
}

function candlePressure(candle) {
  const range = Number(candle.high) - Number(candle.low);
  if (range === 0) return "NEUTRAL";
  const closePosition = (Number(candle.close) - Number(candle.low)) / range;
  if (Number(candle.close) > Number(candle.open) && closePosition >= 0.70) return "BUYING";
  if (Number(candle.close) < Number(candle.open) && closePosition <= 0.30) return "SELLING";
  return "NEUTRAL";
}

function zoneBias(close, support, resistance) {
  const values = [];
  if (support) {
    if (support.high >= close) {
      const distance = Math.max(close - support.high, 0);
      const width = Math.max(support.high - support.low, close * 0.001, 1e-9);
      values.push(Math.max(-1, 1 - distance / width));
    } else {
      const distance = (close - support.high) / Math.max(Math.abs(close), 1e-9);
      values.push(Math.max(-0.25, 0.5 - distance * 50));
    }
  }
  if (resistance) {
    if (resistance.low <= close) {
      const distance = Math.max(resistance.low - close, 0);
      const width = Math.max(resistance.high - resistance.low, close * 0.001, 1e-9);
      values.push(Math.min(1, -1 + distance / width));
    } else {
      const distance = (resistance.low - close) / Math.max(Math.abs(close), 1e-9);
      values.push(Math.min(0.25, -0.5 + distance * 50));
    }
  }
  return values.length ? mean(values) : 0;
}

function normalise(up, flat, down) {
  const values = [Math.max(0, up), Math.max(0, flat), Math.max(0, down)];
  const total = values.reduce((sum, value) => sum + value, 0);
  return values.map((value) => value / total);
}

export function forecast(candles, horizons = [1, 3, 5], support = null, resistance = null) {
  validateCandles(candles);
  for (let i = 0; i < horizons.length; i += 1) {
    if (horizons[i] < 1) throw new Error("horizons must be positive");
    if (i > 0 && horizons[i - 1] >= horizons[i]) throw new Error("horizons must be strictly increasing");
  }

  const latest = candles[candles.length - 1];
  const close = Number(latest.close);
  const returns = returnsOf(candles);
  const trend = trendBias(returns);
  const pressure = candlePressure(latest);
  const pressureBias = { BUYING: 0.18, SELLING: -0.18, NEUTRAL: 0 }[pressure];
  const directionalZoneBias = zoneBias(close, support, resistance);
  const results = [];

  for (const horizon of horizons) {
    let [up, flat, down, empirical] = empiricalDirection(returns, horizon);
    const directionalBias = Math.max(-0.35, Math.min(0.35, trend * 0.45 + pressureBias + directionalZoneBias * 0.20));
    [up, flat, down] = normalise(up + directionalBias, flat, down - directionalBias);
    const recentAbs = returns.length ? mean(returns.slice(-20).map((value) => Math.abs(value))) : 0;
    const expected = empirical + directionalBias * recentAbs * horizon;
    results.push({
      horizon,
      up_probability: up,
      flat_probability: flat,
      down_probability: down,
      expected_return: expected,
      expected_close: close * (1 + expected),
      direction: up >= flat && up >= down ? UP : flat >= down ? FLAT : DOWN,
    });
  }

  const first = results[0];
  const directionalStrength = Math.abs(first.up_probability - first.down_probability);
  const sampleFactor = Math.min(1, returns.length / 100);
  const confidence = Math.max(0, Math.min(1, 0.45 * directionalStrength + 0.55 * sampleFactor));
  const scenarios = [
    { name: "bullish-continuation", probability: first.up_probability, path: ["TEST_SUPPORT", "REJECT/RECLAIM", "BULLISH_CONFIRM"] },
    { name: "bearish-continuation", probability: first.down_probability, path: ["TEST_RESISTANCE", "REJECT/RECLAIM", "BEARISH_CONFIRM"] },
    { name: "range/unclear", probability: first.flat_probability, path: ["TEST", "NO_CLEAR_CONFIRMATION", "WAIT"] },
  ].sort((a, b) => b.probability - a.probability);

  return {
    as_of: latest.time ?? latest.datetime ?? null,
    current_close: close,
    horizons: results,
    scenarios,
    confidence,
    model: "deterministic-empirical-v1",
  };
}

export function supervise(signal, forecastResult = null, mtf = null, minConfidence = 0.45) {
  if (!(minConfidence >= 0 && minConfidence <= 1)) throw new Error("min_confidence must be between 0 and 1");
  const reasons = [];
  if (signal.action === "WAIT") return { action: "WAIT", allowed: false, reasons: ["strategy is WAIT"] };
  if (!["LONG", "SHORT"].includes(signal.action)) return { action: "WAIT", allowed: false, reasons: ["unknown strategy action"] };

  if (signal.protection !== "SAFE") reasons.push("protection is not SAFE");
  if (!["NO_BREAKOUT", ""].includes(signal.breakoutState)) reasons.push(`breakout state is ${signal.breakoutState}`);

  if (forecastResult === null) reasons.push("forecast unavailable");
  else {
    if (forecastResult.confidence < minConfidence) reasons.push("forecast confidence below threshold");
    const first = forecastResult.horizons[0] ?? null;
    if (first === null) reasons.push("forecast horizon unavailable");
    else if (signal.action === "LONG" && first.direction === DOWN) reasons.push("LONG conflicts with near-horizon DOWN forecast");
    else if (signal.action === "SHORT" && first.direction === UP) reasons.push("SHORT conflicts with near-horizon UP forecast");
  }

  if (mtf) {
    if (signal.action === "LONG" && mtf.alignment === "BEARISH") reasons.push("LONG conflicts with bearish MTF alignment");
    else if (signal.action === "SHORT" && mtf.alignment === "BULLISH") reasons.push("SHORT conflicts with bullish MTF alignment");
  }

  if (reasons.length) return { action: "WAIT", allowed: false, reasons };
  return { action: ALLOW, allowed: true, reasons: ["all realtime consistency checks passed"] };
}
