/**
 * Canonical Worker-side implementation of the Python realtime signal contract.
 *
 * This module intentionally mirrors strategy/candles.py, levels_v2.py,
 * fake_breakout.py, market_structure.py, sequence.py, timeframe.py, and
 * scoring.py for the single-timeframe Webaria signal endpoint.
 *
 * It is research/paper-only. It never places broker orders.
 */

export const LONG = "LONG";
export const SHORT = "SHORT";
export const WAIT = "WAIT";
export const SUPPORT = "SUPPORT";
export const RESISTANCE = "RESISTANCE";
export const NO_BREAKOUT = "NO_BREAKOUT";
export const FAKE_BREAKOUT = "FAKE_BREAKOUT";
export const TRUE_BREAKOUT = "TRUE_BREAKOUT";
export const BREAKOUT_WAIT = "WAIT";
export const BULLISH = "BULLISH";
export const BEARISH = "BEARISH";
export const RANGE = "RANGE";
export const UNKNOWN = "UNKNOWN";
export const HH = "HH";
export const HL = "HL";
export const LH = "LH";
export const LL = "LL";

export const TIMEFRAME_CONFIG = Object.freeze({
  "1m": { interval: "1min", lookback: 30, rangeMultiplier: 0.80, minZoneDistance: 0.00005, maxZoneDistance: 0.00100, confirmationMultiplier: 0.20 },
  "5m": { interval: "5min", lookback: 30, rangeMultiplier: 0.80, minZoneDistance: 0.00008, maxZoneDistance: 0.00150, confirmationMultiplier: 0.20 },
  "15m": { interval: "15min", lookback: 30, rangeMultiplier: 0.35, minZoneDistance: 0.00010, maxZoneDistance: 0.00250, confirmationMultiplier: 0.20 },
  "30m": { interval: "30min", lookback: 30, rangeMultiplier: 0.85, minZoneDistance: 0.00012, maxZoneDistance: 0.00350, confirmationMultiplier: 0.20 },
  "1h": { interval: "1h", lookback: 30, rangeMultiplier: 0.90, minZoneDistance: 0.00015, maxZoneDistance: 0.00500, confirmationMultiplier: 0.20 },
  "4h": { interval: "4h", lookback: 30, rangeMultiplier: 0.95, minZoneDistance: 0.00020, maxZoneDistance: 0.01000, confirmationMultiplier: 0.20 },
  "1D": { interval: "1day", lookback: 30, rangeMultiplier: 1.00, minZoneDistance: 0.00030, maxZoneDistance: 0.02000, confirmationMultiplier: 0.20 },
});

const MAX_API_BARS = 120;
const DEFAULT_OUTPUT_SIZE = 100;
const MAX_TEST_AGE = 3;
const SWING_STRENGTH = 2;
const MIN_REACTION_GAP = 2;
const MIN_TOUCHES = 2;

export class BadRequest extends Error {}

function finiteNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new BadRequest(`${name} must be a finite number`);
  return number;
}

export function validateCandle(raw) {
  const open = finiteNumber(raw.open, "open");
  const high = finiteNumber(raw.high, "high");
  const low = finiteNumber(raw.low, "low");
  const close = finiteNumber(raw.close, "close");
  if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) {
    throw new BadRequest("invalid OHLC relationship");
  }
  return { open, high, low, close, datetime: raw.datetime ?? raw.time ?? null };
}

export function candlePressure(candle) {
  const range = candle.high - candle.low;
  if (range === 0) return "NEUTRAL";
  const closePosition = (candle.close - candle.low) / range;
  if (candle.close > candle.open && closePosition >= 0.70) return "BUYING";
  if (candle.close < candle.open && closePosition <= 0.30) return "SELLING";
  return "NEUTRAL";
}

export function rejectionPressure(candle, direction) {
  const upperWick = candle.high - Math.max(candle.open, candle.close);
  const lowerWick = Math.min(candle.open, candle.close) - candle.low;
  if (direction === LONG) return candlePressure(candle) === "BUYING" && lowerWick >= upperWick;
  if (direction === SHORT) return candlePressure(candle) === "SELLING" && upperWick >= lowerWick;
  throw new ValueError("direction must be LONG or SHORT");
}

export function averageRange(candles, lookback) {
  if (lookback < 1) throw new BadRequest("lookback must be >= 1");
  const sample = candles.slice(-lookback);
  if (!sample.length) return 0;
  return sample.reduce((sum, candle) => sum + (candle.high - candle.low), 0) / sample.length;
}

export function adaptiveZoneTolerance(candles, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  const value = averageRange(candles, config.lookback) * config.rangeMultiplier;
  return Math.min(config.maxZoneDistance, Math.max(config.minZoneDistance, value));
}

export function adaptiveConfirmationBuffer(candles, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  if (!config) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  const value = averageRange(candles, config.lookback) * config.confirmationMultiplier;
  return Math.max(config.minZoneDistance * 0.5, value);
}

export function confirmedSwingLows(candles, strength = SWING_STRENGTH) {
  if (strength < 1) throw new BadRequest("strength must be >= 1");
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const low = candles[i].low;
    let unique = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].low <= low) {
        unique = false;
        break;
      }
    }
    if (unique) result.push([i, low]);
  }
  return result;
}

export function confirmedSwingHighs(candles, strength = SWING_STRENGTH) {
  if (strength < 1) throw new BadRequest("strength must be >= 1");
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const high = candles[i].high;
    let unique = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].high >= high) {
        unique = false;
        break;
      }
    }
    if (unique) result.push([i, high]);
  }
  return result;
}

function cluster(prices, tolerance) {
  if (!(tolerance > 0) || !Number.isFinite(tolerance)) throw new BadRequest("tolerance must be finite and > 0");
  const clusters = [];
  for (const price of [...prices].sort((a, b) => a - b)) {
    if (!clusters.length || price - clusters[clusters.length - 1][0] > tolerance) clusters.push([price]);
    else clusters[clusters.length - 1].push(price);
  }
  return clusters;
}

function buildSwingZones(swings, kind, tolerance, minTouches = MIN_TOUCHES, minReactionGap = MIN_REACTION_GAP) {
  if (minReactionGap < 1) throw new BadRequest("minReactionGap must be >= 1");
  const zones = [];
  for (const priceCluster of cluster(swings.map((entry) => entry[1]), tolerance)) {
    const clusterSwings = swings
      .filter((swing) => priceCluster.some((price) => price === swing[1]))
      .sort((a, b) => a[0] - b[0]);
    const selected = [];
    for (const swing of clusterSwings) {
      if (!selected.length || swing[0] - selected[selected.length - 1][0] >= minReactionGap) selected.push(swing);
    }
    if (selected.length < minTouches) continue;
    const prices = selected.map((entry) => entry[1]);
    const low = Math.min(...prices) - tolerance;
    const high = Math.max(...prices) + tolerance;
    zones.push({ low, high, center: (low + high) / 2, kind, touches: selected.length });
  }
  return zones;
}

export function findSupportZones(candles, tolerance) {
  return buildSwingZones(confirmedSwingLows(candles), SUPPORT, tolerance);
}

export function findResistanceZones(candles, tolerance) {
  return buildSwingZones(confirmedSwingHighs(candles), RESISTANCE, tolerance);
}

export function classifySupportBreakout(candle, support, confirmationBuffer) {
  if (support.kind !== SUPPORT) throw new BadRequest("zone must be SUPPORT");
  if (confirmationBuffer < 0) throw new BadRequest("confirmationBuffer must be >= 0");
  if (candle.low >= support.low) return { state: NO_BREAKOUT, reason: "price did not break below support" };
  if (candle.close >= support.low) return { state: FAKE_BREAKOUT, reason: "price broke below support intrabar but closed back above it" };
  if (candle.close <= support.low - confirmationBuffer) return { state: TRUE_BREAKOUT, reason: "candle closed clearly below support" };
  return { state: BREAKOUT_WAIT, reason: "support was breached but the close is not decisive" };
}

export function classifyResistanceBreakout(candle, resistance, confirmationBuffer) {
  if (resistance.kind !== RESISTANCE) throw new BadRequest("zone must be RESISTANCE");
  if (confirmationBuffer < 0) throw new BadRequest("confirmationBuffer must be >= 0");
  if (candle.high <= resistance.high) return { state: NO_BREAKOUT, reason: "price did not break above resistance" };
  if (candle.close <= resistance.high) return { state: FAKE_BREAKOUT, reason: "price broke above resistance intrabar but closed back below it" };
  if (candle.close >= resistance.high + confirmationBuffer) return { state: TRUE_BREAKOUT, reason: "candle closed clearly above resistance" };
  return { state: BREAKOUT_WAIT, reason: "resistance was breached but the close is not decisive" };
}

function touches(candle, zone) {
  return candle.low <= zone.high && candle.high >= zone.low;
}

export function evaluateSequence(candles, zone, timeframe, direction, maxTestAge = MAX_TEST_AGE) {
  if (!(direction === LONG || direction === SHORT)) throw new BadRequest("direction must be LONG or SHORT");
  if (direction === LONG && zone.kind !== SUPPORT) throw new BadRequest("LONG requires SUPPORT");
  if (direction === SHORT && zone.kind !== RESISTANCE) throw new BadRequest("SHORT requires RESISTANCE");
  if (maxTestAge < 1) throw new BadRequest("maxTestAge must be >= 1");
  if (candles.length < 2) return { action: WAIT, state: "APPROACH", reason: "not enough completed candles", breakoutState: NO_BREAKOUT };

  const buffer = adaptiveConfirmationBuffer(candles.slice(0, -1), timeframe);
  const currentIndex = candles.length - 1;
  const current = candles[currentIndex];
  const start = Math.max(0, currentIndex - maxTestAge);

  for (let testIndex = currentIndex - 1; testIndex >= start; testIndex -= 1) {
    const test = candles[testIndex];
    if (!touches(test, zone)) continue;

    if (direction === LONG) {
      const breakout = classifySupportBreakout(test, zone, buffer);
      if (breakout.state === TRUE_BREAKOUT) {
        return { action: WAIT, state: "BROKEN", reason: "support closed decisively below the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
      }
      if (breakout.state === BREAKOUT_WAIT) continue;
      const reclaim = breakout.state === FAKE_BREAKOUT;
      const rejection = breakout.state === NO_BREAKOUT && test.close > zone.high && rejectionPressure(test, LONG);
      if (!reclaim && !rejection) continue;
      if (candlePressure(current) !== "BUYING") {
        return { action: WAIT, state: "CONFIRM", reason: "support reacted but confirmation candle is not strongly bullish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
      }
      if (current.close <= zone.high) {
        return { action: WAIT, state: "CONFIRM", reason: "buyers have not confirmed a close above support", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
      }
      return { action: LONG, state: "CONFIRM", reason: "support test followed by bullish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout.state };
    }

    const breakout = classifyResistanceBreakout(test, zone, buffer);
    if (breakout.state === TRUE_BREAKOUT) {
      return { action: WAIT, state: "BROKEN", reason: "resistance closed decisively above the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
    }
    if (breakout.state === BREAKOUT_WAIT) continue;
    const reclaim = breakout.state === FAKE_BREAKOUT;
    const rejection = breakout.state === NO_BREAKOUT && test.close < zone.low && rejectionPressure(test, SHORT);
    if (!reclaim && !rejection) continue;
    if (candlePressure(current) !== "SELLING") {
      return { action: WAIT, state: "CONFIRM", reason: "resistance reacted but confirmation candle is not strongly bearish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
    }
    if (current.close >= zone.low) {
      return { action: WAIT, state: "CONFIRM", reason: "sellers have not confirmed a close below resistance", testIndex, confirmationIndex: currentIndex, breakoutState: breakout.state };
    }
    return { action: SHORT, state: "CONFIRM", reason: "resistance test followed by bearish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout.state };
  }

  return { action: WAIT, state: "APPROACH", reason: "no complete test-and-confirmation sequence", breakoutState: NO_BREAKOUT };
}

export function analyzeMarketStructure(candles, strength = SWING_STRENGTH) {
  const rawHighs = confirmedSwingHighs(candles, strength);
  const rawLows = confirmedSwingLows(candles, strength);
  const highs = rawHighs.map(([index, price], position, all) => ({ index, price, kind: !position || price > all[position - 1][1] ? HH : LH }));
  const lows = rawLows.map(([index, price], position, all) => ({ index, price, kind: !position || price > all[position - 1][1] ? HL : LL }));
  let bias = UNKNOWN;
  if (highs.length >= 2 && lows.length >= 2) {
    if (highs[highs.length - 1].kind === HH && lows[lows.length - 1].kind === HL) bias = BULLISH;
    else if (highs[highs.length - 1].kind === LH && lows[lows.length - 1].kind === LL) bias = BEARISH;
    else bias = RANGE;
  }
  return { bias, highs, lows };
}

export function scoreSetup(direction, zoneTouches, structureBias, breakoutState, confirmationStrength = 20) {
  const zone = Math.min(25, zoneTouches * 5);
  const expected = direction === LONG ? BULLISH : BEARISH;
  const structure = structureBias === expected ? 20 : 0;
  const breakout = breakoutState === NO_BREAKOUT ? 20 : breakoutState === FAKE_BREAKOUT ? 25 : 0;
  const mtf = 0;
  const total = zone + structure + breakout + confirmationStrength + mtf;
  return {
    total,
    zone,
    structure,
    breakout,
    confirmation: confirmationStrength,
    mtf,
    reasons: [
      `zone touches=${zoneTouches}: ${zone}/25`,
      `structure=${structureBias}: ${structure}/20`,
      `breakout=${breakoutState}: ${breakout}/25`,
      `confirmation=${confirmationStrength}/20`,
      "mtf=UNAVAILABLE: 0/10",
    ],
  };
}

function stopReference(zone, direction, candles, timeframe) {
  const buffer = adaptiveConfirmationBuffer(candles, timeframe);
  return direction === LONG ? zone.low - buffer : zone.high + buffer;
}

function bestSignal(signals) {
  if (!signals.length) throw new BadRequest("no candidate zones");
  return [...signals].sort((a, b) => {
    const aKey = [a.result.action !== WAIT ? 1 : 0, a.score?.total ?? -1, a.result.entryReference ?? 0];
    const bKey = [b.result.action !== WAIT ? 1 : 0, b.score?.total ?? -1, b.result.entryReference ?? 0];
    for (let i = 0; i < aKey.length; i += 1) {
      if (aKey[i] !== bKey[i]) return bKey[i] - aKey[i];
    }
    return 0;
  })[0];
}

function selectSignal(longSignal, shortSignal) {
  const longOk = longSignal.action === LONG;
  const shortOk = shortSignal.action === SHORT;
  if (longOk && !shortOk) return longSignal;
  if (shortOk && !longOk) return shortSignal;
  if (longOk && shortOk) {
    const longScore = longSignal.score?.total ?? -1;
    const shortScore = shortSignal.score?.total ?? -1;
    if (longScore !== shortScore) return longScore > shortScore ? longSignal : shortSignal;
  }
  return { action: WAIT, reason: "no unambiguous realtime setup", timeframe: longSignal.timeframe };
}

function nearestSupport(price, zones) {
  const candidates = zones.filter((zone) => zone.center <= price || (zone.low <= price && price <= zone.high));
  candidates.sort((a, b) => {
    const ad = a.low <= price && price <= a.high ? 0 : price - a.high;
    const bd = b.low <= price && price <= b.high ? 0 : price - b.high;
    if (ad !== bd) return ad - bd;
    return b.touches - a.touches;
  });
  return candidates[0] ?? null;
}

function nearestResistance(price, zones) {
  const candidates = zones.filter((zone) => zone.center >= price || (zone.low <= price && price <= zone.high));
  candidates.sort((a, b) => {
    const ad = a.low <= price && price <= a.high ? 0 : a.low - price;
    const bd = b.low <= price && price <= b.high ? 0 : b.low - price;
    if (ad !== bd) return ad - bd;
    return b.touches - a.touches;
  });
  return candidates[0] ?? null;
}

export function evaluateRealtimeSignal(rawCandles, timeframe) {
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  const candles = rawCandles.map(validateCandle);
  if (candles.length < 5) throw new BadRequest("not enough completed candles for evaluation");

  const history = candles.slice(0, -1);
  const tolerance = adaptiveZoneTolerance(history, timeframe);
  const supports = findSupportZones(history, tolerance);
  const resistances = findResistanceZones(history, tolerance);
  const structure = analyzeMarketStructure(history);

  const longCandidates = supports.map((zone) => {
    const result = evaluateSequence(candles, zone, timeframe, LONG);
    return {
      direction: LONG,
      zone,
      result,
      score: result.action === LONG ? scoreSetup(LONG, zone.touches, structure.bias, result.breakoutState, 20) : null,
    };
  });
  const shortCandidates = resistances.map((zone) => {
    const result = evaluateSequence(candles, zone, timeframe, SHORT);
    return {
      direction: SHORT,
      zone,
      result,
      score: result.action === SHORT ? scoreSetup(SHORT, zone.touches, structure.bias, result.breakoutState, 20) : null,
    };
  });

  const longSignal = bestSignal(longCandidates);
  const shortSignal = bestSignal(shortCandidates);
  const selected = selectSignal(longSignal, shortSignal);
  const selectedScore = selected.action === LONG || selected.action === SHORT ? selected.score ?? null : null;
  const currentPrice = candles[candles.length - 1].close;
  const support = nearestSupport(currentPrice, supports);
  const resistance = nearestResistance(currentPrice, resistances);

  return {
    signal: selected.action,
    state: selected.state ?? "APPROACH",
    reason: selected.reason,
    price: currentPrice,
    structure_bias: structure.bias,
    zone: selected.zone ?? null,
    entry_reference: selected.result?.entryReference ?? null,
    stop_reference: selected.zone && selected.action !== WAIT
      ? stopReference(selected.zone, selected.action, history, timeframe)
      : null,
    breakout_state: selected.result?.breakoutState ?? NO_BREAKOUT,
    score: selectedScore,
    support,
    resistance,
    candles,
    candles_used: candles.length,
  };
}

export async function fetchTwelveData(symbol, timeframe, apiKey) {
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("interval", TIMEFRAME_CONFIG[timeframe].interval);
  url.searchParams.set("outputsize", String(DEFAULT_OUTPUT_SIZE));
  url.searchParams.set("timezone", "UTC");
  url.searchParams.set("apikey", apiKey);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`market data provider returned HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || !Array.isArray(payload.values)) throw new Error(payload.message || "market data provider returned an invalid response");
    const completed = payload.values.slice(1, MAX_API_BARS + 1).map((raw) => validateCandle({ open: raw.open, high: raw.high, low: raw.low, close: raw.close, datetime: raw.datetime })).reverse();
    if (completed.length < 10) throw new Error("not enough completed candles returned by the provider");
    return completed;
  } finally {
    clearTimeout(timeout);
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export async function handleSignalParity(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);

  const candles = await fetchTwelveData(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  const result = evaluateRealtimeSignal(candles, timeframe);
  return json({
    symbol,
    timeframe,
    ...result,
    generated_at: new Date().toISOString(),
    execution: "NONE",
  });
}
