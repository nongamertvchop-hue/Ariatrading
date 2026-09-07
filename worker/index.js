/**
 * Webaria Worker API.
 *
 * Workers equivalent of the Pages Function requested for this project.
 * Serves /api/signal and delegates every other request to Webaria assets.
 *
 * Market data: Twelve Data time_series API.
 * Signal path: JavaScript port of the repository's indicator-free core
 * sequence, swing-zone discovery, market-structure bias, and setup score.
 *
 * No order execution happens here.
 */

const LONG = "LONG";
const SHORT = "SHORT";
const WAIT = "WAIT";
const SUPPORT = "SUPPORT";
const RESISTANCE = "RESISTANCE";
const NO_BREAKOUT = "NO_BREAKOUT";
const FAKE_BREAKOUT = "FAKE_BREAKOUT";
const TRUE_BREAKOUT = "TRUE_BREAKOUT";
const BREAKOUT_WAIT = "WAIT";
const BULLISH = "BULLISH";
const BEARISH = "BEARISH";
const RANGE = "RANGE";
const UNKNOWN = "UNKNOWN";
const HH = "HH";
const HL = "HL";
const LH = "LH";
const LL = "LL";

const TIMEFRAME_CONFIG = Object.freeze({
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

class BadRequest extends Error {}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function finiteNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new BadRequest(`${name} must be a finite number`);
  return number;
}

function validateCandle(raw) {
  const open = finiteNumber(raw.open, "open");
  const high = finiteNumber(raw.high, "high");
  const low = finiteNumber(raw.low, "low");
  const close = finiteNumber(raw.close, "close");
  if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) {
    throw new BadRequest("invalid OHLC relationship");
  }
  return { open, high, low, close, datetime: raw.datetime ?? null };
}

function candlePressure(candle) {
  const range = candle.high - candle.low;
  if (range === 0) return "NEUTRAL";
  const closePosition = (candle.close - candle.low) / range;
  if (candle.close > candle.open && closePosition >= 0.70) return "BUYING";
  if (candle.close < candle.open && closePosition <= 0.30) return "SELLING";
  return "NEUTRAL";
}

function rejectionPressure(candle, direction) {
  const upperWick = candle.high - Math.max(candle.open, candle.close);
  const lowerWick = Math.min(candle.open, candle.close) - candle.low;
  if (direction === LONG) return candlePressure(candle) === "BUYING" && lowerWick >= upperWick;
  if (direction === SHORT) return candlePressure(candle) === "SELLING" && upperWick >= lowerWick;
  throw new Error("direction must be LONG or SHORT");
}

function averageRange(candles, lookback) {
  const sample = candles.slice(-lookback);
  if (!sample.length) return 0;
  return sample.reduce((sum, candle) => sum + (candle.high - candle.low), 0) / sample.length;
}

function adaptiveZoneTolerance(candles, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  const value = averageRange(candles, config.lookback) * config.rangeMultiplier;
  return Math.min(config.maxZoneDistance, Math.max(config.minZoneDistance, value));
}

function adaptiveConfirmationBuffer(candles, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  const value = averageRange(candles, config.lookback) * config.confirmationMultiplier;
  return Math.max(config.minZoneDistance * 0.5, value);
}

function confirmedSwingLows(candles, strength = SWING_STRENGTH) {
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const low = candles[i].low;
    let unique = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].low <= low) { unique = false; break; }
    }
    if (unique) result.push([i, low]);
  }
  return result;
}

function confirmedSwingHighs(candles, strength = SWING_STRENGTH) {
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const high = candles[i].high;
    let unique = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].high >= high) { unique = false; break; }
    }
    if (unique) result.push([i, high]);
  }
  return result;
}

function cluster(prices, tolerance) {
  if (!(tolerance > 0) || !Number.isFinite(tolerance)) throw new BadRequest("tolerance must be finite and > 0");
  const sorted = [...prices].sort((a, b) => a - b);
  const clusters = [];
  for (const price of sorted) {
    if (!clusters.length || price - clusters[clusters.length - 1][0] > tolerance) clusters.push([price]);
    else clusters[clusters.length - 1].push(price);
  }
  return clusters;
}

function buildSwingZones(swings, kind, tolerance) {
  const zones = [];
  for (const priceCluster of cluster(swings.map((entry) => entry[1]), tolerance)) {
    const selected = [];
    for (const swing of swings) {
      if (!priceCluster.includes(swing[1])) continue;
      if (!selected.length || swing[0] - selected[selected.length - 1][0] >= MIN_REACTION_GAP) selected.push(swing);
    }
    if (selected.length < MIN_TOUCHES) continue;
    const prices = selected.map((entry) => entry[1]);
    zones.push({ low: Math.min(...prices) - tolerance, high: Math.max(...prices) + tolerance, center: (Math.min(...prices) + Math.max(...prices)) / 2, kind, touches: selected.length });
  }
  return zones;
}

function findZones(candles, timeframe) {
  const tolerance = adaptiveZoneTolerance(candles, timeframe);
  return [...buildSwingZones(confirmedSwingLows(candles), SUPPORT, tolerance), ...buildSwingZones(confirmedSwingHighs(candles), RESISTANCE, tolerance)];
}

function touches(candle, zone) { return candle.low <= zone.high && candle.high >= zone.low; }

function classifySupportBreakout(candle, zone, buffer) {
  if (candle.close < zone.low - buffer) return TRUE_BREAKOUT;
  if (candle.low < zone.low - buffer && candle.close > zone.high) return FAKE_BREAKOUT;
  if (candle.low < zone.low - buffer && candle.close <= zone.high) return BREAKOUT_WAIT;
  return NO_BREAKOUT;
}

function classifyResistanceBreakout(candle, zone, buffer) {
  if (candle.close > zone.high + buffer) return TRUE_BREAKOUT;
  if (candle.high > zone.high + buffer && candle.close < zone.low) return FAKE_BREAKOUT;
  if (candle.high > zone.high + buffer && candle.close >= zone.low) return BREAKOUT_WAIT;
  return NO_BREAKOUT;
}

function evaluateSequence(candles, zone, timeframe, direction, maxTestAge = MAX_TEST_AGE) {
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
      if (breakout === TRUE_BREAKOUT) return { action: WAIT, state: "BROKEN", reason: "support closed decisively below the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      if (breakout === BREAKOUT_WAIT) continue;
      const reclaim = breakout === FAKE_BREAKOUT;
      const rejection = breakout === NO_BREAKOUT && test.close > zone.high && rejectionPressure(test, LONG);
      if (!reclaim && !rejection) continue;
      if (candlePressure(current) !== "BUYING") return { action: WAIT, state: "CONFIRM", reason: "support reacted but confirmation candle is not strongly bullish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      if (current.close <= zone.high) return { action: WAIT, state: "CONFIRM", reason: "buyers have not confirmed a close above support", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      return { action: LONG, state: "CONFIRM", reason: "support test followed by bullish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout };
    }
    const breakout = classifyResistanceBreakout(test, zone, buffer);
    if (breakout === TRUE_BREAKOUT) return { action: WAIT, state: "BROKEN", reason: "resistance closed decisively above the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    if (breakout === BREAKOUT_WAIT) continue;
    const reclaim = breakout === FAKE_BREAKOUT;
    const rejection = breakout === NO_BREAKOUT && test.close < zone.low && rejectionPressure(test, SHORT);
    if (!reclaim && !rejection) continue;
    if (candlePressure(current) !== "SELLING") return { action: WAIT, state: "CONFIRM", reason: "resistance reacted but confirmation candle is not strongly bearish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    if (current.close >= zone.low) return { action: WAIT, state: "CONFIRM", reason: "sellers have not confirmed a close below resistance", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    return { action: SHORT, state: "CONFIRM", reason: "resistance test followed by bearish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout };
  }
  return { action: WAIT, state: "APPROACH", reason: "no complete test-and-confirmation sequence", breakoutState: NO_BREAKOUT };
}

function analyzeMarketStructure(candles, strength = SWING_STRENGTH) {
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

function setupScore(direction, zoneTouches, structureBias, breakoutState, confirmationStrength = 20) {
  const zone = Math.min(25, zoneTouches * 5);
  const expected = direction === LONG ? BULLISH : BEARISH;
  const structure = structureBias === expected ? 20 : 0;
  let breakout = 0;
  if (breakoutState === NO_BREAKOUT) breakout = 20;
  else if (breakoutState === FAKE_BREAKOUT) breakout = 25;
  const total = zone + structure + breakout + confirmationStrength;
  return { total, zone, structure, breakout, confirmation: confirmationStrength, mtf: 0, reasons: [`zone touches=${zoneTouches}: ${zone}/25`, `structure=${structureBias}: ${structure}/20`, `breakout=${breakoutState}: ${breakout}/25`, `confirmation=${confirmationStrength}/20`, "mtf=UNAVAILABLE: 0/10"] };
}

function nearestZone(zones, currentPrice, kind) {
  const candidates = zones.filter((zone) => kind === SUPPORT ? zone.low <= currentPrice : zone.high >= currentPrice);
  if (!candidates.length) return null;
  return candidates.sort((a, b) => Math.abs(a.center - currentPrice) - Math.abs(b.center - currentPrice))[0];
}

function stopReference(zone, direction, candles, timeframe) {
  const buffer = adaptiveConfirmationBuffer(candles, timeframe);
  return direction === LONG ? zone.low - buffer : zone.high + buffer;
}

async function fetchTwelveData(symbol, timeframe, apiKey) {
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
    const completed = payload.values.slice(1, MAX_API_BARS + 1).map(validateCandle).reverse();
    if (completed.length < 10) throw new Error("not enough completed candles returned by the provider");
    return completed;
  } finally { clearTimeout(timeout); }
}

async function fetchLivePrice(symbol, apiKey) {
  const url = new URL("https://api.twelvedata.com/price");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("apikey", apiKey);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`market price provider returned HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || payload.price == null) throw new Error(payload.message || "market price provider returned an invalid response");
    return finiteNumber(payload.price, "price");
  } finally { clearTimeout(timeout); }
}

async function fetchLiveCandle(symbol, timeframe, apiKey) {
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("interval", TIMEFRAME_CONFIG[timeframe].interval);
  url.searchParams.set("outputsize", "2");
  url.searchParams.set("timezone", "UTC");
  url.searchParams.set("apikey", apiKey);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`market data provider returned HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || !Array.isArray(payload.values)) throw new Error(payload.message || "market data provider returned an invalid response");
    if (!payload.values.length) throw new Error("market data provider returned no live candle");
    const raw = payload.values[0];
    return validateCandle({ open: raw.open, high: raw.high, low: raw.low, close: raw.close, datetime: raw.datetime });
  } finally { clearTimeout(timeout); }
}

async function handleLivePrice(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);
  const price = await fetchLivePrice(symbol, env.TWELVE_DATA_API_KEY);
  return json({ symbol, price, generated_at: new Date().toISOString(), execution: "NONE" });
}

async function handleLiveCandle(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!Object.prototype.hasOwnProperty.call(TIMEFRAME_CONFIG, timeframe)) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);
  const candle = await fetchLiveCandle(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  return json({ symbol, timeframe, candle, confirmed: false, generated_at: new Date().toISOString(), execution: "NONE" });
}

async function handleSignal(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!Object.prototype.hasOwnProperty.call(TIMEFRAME_CONFIG, timeframe)) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);
  const candles = await fetchTwelveData(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  const currentPrice = candles[candles.length - 1].close;
  const zones = findZones(candles, timeframe);
  const support = nearestZone(zones, currentPrice, SUPPORT);
  const resistance = nearestZone(zones, currentPrice, RESISTANCE);
  const structure = analyzeMarketStructure(candles.slice(0, -1));
  const candidates = [];
  if (support) candidates.push({ direction: LONG, zone: support, result: evaluateSequence(candles, support, timeframe, LONG) });
  if (resistance) candidates.push({ direction: SHORT, zone: resistance, result: evaluateSequence(candles, resistance, timeframe, SHORT) });
  const actionable = candidates.filter((candidate) => candidate.result.action === candidate.direction).map((candidate) => ({ ...candidate, score: setupScore(candidate.direction, candidate.zone.touches, structure.bias, candidate.result.breakoutState) })).sort((a, b) => b.score.total - a.score.total)[0];
  const selected = actionable || candidates[0] || null;
  const result = selected?.result || { action: WAIT, state: "APPROACH", reason: "no confirmed support/resistance zones", breakoutState: NO_BREAKOUT };
  const score = selected && result.action === selected.direction ? setupScore(selected.direction, selected.zone.touches, structure.bias, result.breakoutState) : null;
  return json({ symbol, timeframe, signal: result.action, state: result.state, reason: result.reason, price: currentPrice, structure_bias: structure.bias, zone: selected?.zone ?? null, entry_reference: result.entryReference ?? null, stop_reference: selected?.zone && result.action === selected.direction ? stopReference(selected.zone, selected.direction, candles.slice(0, -1), timeframe) : null, breakout_state: result.breakoutState, score, candles, candles_used: candles.length, generated_at: new Date().toISOString(), execution: "NONE" });
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (url.pathname === "/api/signal") return await handleSignal(request, env);
      if (url.pathname === "/api/price") return await handleLivePrice(request, env);
      if (url.pathname === "/api/live-candle") return await handleLiveCandle(request, env);
      return env.ASSETS.fetch(request);
    } catch (error) {
      if (error instanceof BadRequest) return json({ error: "bad_request", message: error.message }, 400);
      if (error?.name === "AbortError") return json({ error: "upstream_timeout", message: "market data request timed out" }, 504);
      return json({ error: "upstream_or_internal_error", message: error?.message || "unknown error" }, 502);
    }
  },
};
