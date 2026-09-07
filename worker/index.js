/**
 * Webaria Worker API.
 *
 * This is the Workers equivalent of a Pages Function for the current
 * deployment model. It serves /api/signal and delegates all other requests
 * to the Webaria static-asset bundle.
 *
 * Market data: Twelve Data time_series API.
 * Signal logic: a JavaScript port of the repository's indicator-free
 * APPROACH -> TEST -> RECLAIM/REJECT -> CONFIRM -> LONG/SHORT sequence.
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

const TIMEFRAME_MAP = Object.freeze({
  "1m": "1min",
  "5m": "5min",
  "15m": "15min",
  "30m": "30min",
  "1h": "1h",
  "4h": "4h",
  "1D": "1day",
});

const MAX_API_BARS = 120;
const DEFAULT_OUTPUT_SIZE = 100;
const MAX_TEST_AGE = 3;
const SWING_STRENGTH = 2;
const MIN_REACTION_GAP = 2;
const MIN_TOUCHES = 2;
const DEFAULT_ZONE_TOLERANCE = 0.001;

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
  if (!Number.isFinite(number)) {
    throw new BadRequest(`${name} must be a finite number`);
  }
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
  if (direction === LONG) {
    return candlePressure(candle) === "BUYING" && lowerWick >= upperWick;
  }
  if (direction === SHORT) {
    return candlePressure(candle) === "SELLING" && upperWick >= lowerWick;
  }
  throw new Error("direction must be LONG or SHORT");
}

function averageRecentRange(candles, lookback = 14) {
  const sample = candles.slice(Math.max(0, candles.length - lookback));
  if (!sample.length) return 0;
  return sample.reduce((sum, candle) => sum + (candle.high - candle.low), 0) / sample.length;
}

function adaptiveBuffer(candles, timeframe) {
  // Mirrors the repository's volatility-adaptive confirmation concept while
  // keeping the public endpoint independent of Python runtime code.
  const recentRange = averageRecentRange(candles, 14);
  const minimum = timeframe === "1D" ? 0.0005 : 0.00005;
  return Math.max(recentRange * 0.10, minimum);
}

function confirmedSwingLows(candles, strength = SWING_STRENGTH) {
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const low = candles[i].low;
    let isUniqueMin = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].low <= low) {
        isUniqueMin = false;
        break;
      }
    }
    if (isUniqueMin) result.push([i, low]);
  }
  return result;
}

function confirmedSwingHighs(candles, strength = SWING_STRENGTH) {
  const result = [];
  for (let i = strength; i < candles.length - strength; i += 1) {
    const high = candles[i].high;
    let isUniqueMax = true;
    for (let j = i - strength; j <= i + strength; j += 1) {
      if (j !== i && candles[j].high >= high) {
        isUniqueMax = false;
        break;
      }
    }
    if (isUniqueMax) result.push([i, high]);
  }
  return result;
}

function cluster(prices, tolerance) {
  if (!(tolerance > 0) || !Number.isFinite(tolerance)) {
    throw new BadRequest("tolerance must be finite and > 0");
  }
  const sorted = [...prices].sort((a, b) => a - b);
  const clusters = [];
  for (const price of sorted) {
    if (!clusters.length || price - clusters[clusters.length - 1][0] > tolerance) {
      clusters.push([price]);
    } else {
      clusters[clusters.length - 1].push(price);
    }
  }
  return clusters;
}

function buildSwingZones(swings, kind, tolerance = DEFAULT_ZONE_TOLERANCE) {
  const zones = [];
  for (const priceCluster of cluster(swings.map((entry) => entry[1]), tolerance)) {
    const selected = [];
    for (const swing of swings) {
      if (!priceCluster.includes(swing[1])) continue;
      if (!selected.length || swing[0] - selected[selected.length - 1][0] >= MIN_REACTION_GAP) {
        selected.push(swing);
      }
    }
    if (selected.length < MIN_TOUCHES) continue;
    const prices = selected.map((entry) => entry[1]);
    zones.push({
      low: Math.min(...prices) - tolerance,
      high: Math.max(...prices) + tolerance,
      kind,
      touches: selected.length,
    });
  }
  return zones;
}

function findZones(candles, tolerance) {
  return [
    ...buildSwingZones(confirmedSwingLows(candles), SUPPORT, tolerance),
    ...buildSwingZones(confirmedSwingHighs(candles), RESISTANCE, tolerance),
  ];
}

function touches(candle, zone) {
  return candle.low <= zone.high && candle.high >= zone.low;
}

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
  if (candles.length < 2) {
    return { action: WAIT, state: "APPROACH", reason: "not enough completed candles", breakoutState: NO_BREAKOUT };
  }
  const buffer = adaptiveBuffer(candles.slice(0, -1), timeframe);
  const currentIndex = candles.length - 1;
  const current = candles[currentIndex];
  const start = Math.max(0, currentIndex - maxTestAge);

  for (let testIndex = currentIndex - 1; testIndex >= start; testIndex -= 1) {
    const test = candles[testIndex];
    if (!touches(test, zone)) continue;

    if (direction === LONG) {
      const breakout = classifySupportBreakout(test, zone, buffer);
      if (breakout === TRUE_BREAKOUT) {
        return { action: WAIT, state: "BROKEN", reason: "support closed decisively below the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      }
      if (breakout === BREAKOUT_WAIT) continue;
      const reclaim = breakout === FAKE_BREAKOUT;
      const rejection = breakout === NO_BREAKOUT && test.close > zone.high && rejectionPressure(test, LONG);
      if (!reclaim && !rejection) continue;
      if (candlePressure(current) !== "BUYING") {
        return { action: WAIT, state: "CONFIRM", reason: "support reacted but confirmation candle is not strongly bullish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      }
      if (current.close <= zone.high) {
        return { action: WAIT, state: "CONFIRM", reason: "buyers have not confirmed a close above support", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
      }
      return { action: LONG, state: "CONFIRM", reason: "support test followed by bullish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout };
    }

    const breakout = classifyResistanceBreakout(test, zone, buffer);
    if (breakout === TRUE_BREAKOUT) {
      return { action: WAIT, state: "BROKEN", reason: "resistance closed decisively above the zone", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    }
    if (breakout === BREAKOUT_WAIT) continue;
    const reclaim = breakout === FAKE_BREAKOUT;
    const rejection = breakout === NO_BREAKOUT && test.close < zone.low && rejectionPressure(test, SHORT);
    if (!reclaim && !rejection) continue;
    if (candlePressure(current) !== "SELLING") {
      return { action: WAIT, state: "CONFIRM", reason: "resistance reacted but confirmation candle is not strongly bearish", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    }
    if (current.close >= zone.low) {
      return { action: WAIT, state: "CONFIRM", reason: "sellers have not confirmed a close below resistance", testIndex, confirmationIndex: currentIndex, breakoutState: breakout };
    }
    return { action: SHORT, state: "CONFIRM", reason: "resistance test followed by bearish confirmation", testIndex, confirmationIndex: currentIndex, entryReference: current.close, breakoutState: breakout };
  }

  return { action: WAIT, state: "APPROACH", reason: "no complete test-and-confirmation sequence", breakoutState: NO_BREAKOUT };
}

function stopReference(zone, direction, candles, timeframe) {
  const buffer = adaptiveBuffer(candles, timeframe);
  return direction === LONG ? zone.low - buffer : zone.high + buffer;
}

function nearestZone(zones, currentPrice, kind) {
  const candidates = zones.filter((zone) => {
    if (kind === SUPPORT) return zone.low <= currentPrice;
    return zone.high >= currentPrice;
  });
  if (!candidates.length) return null;
  return candidates.sort((a, b) => Math.abs(a.center ?? (a.low + a.high) / 2 - currentPrice) - Math.abs(b.center ?? (b.low + b.high) / 2 - currentPrice))[0];
}

async function fetchTwelveData(symbol, timeframe, apiKey) {
  const interval = TIMEFRAME_MAP[timeframe];
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("interval", interval);
  url.searchParams.set("outputsize", String(DEFAULT_OUTPUT_SIZE));
  url.searchParams.set("timezone", "UTC");
  url.searchParams.set("apikey", apiKey);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`market data provider returned HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || !Array.isArray(payload.values)) {
      throw new Error(payload.message || "market data provider returned an invalid response");
    }

    // Twelve Data returns the newest point first. The newest point may be an
    // in-progress candle, so exclude it to preserve the repository's completed
    // candle / no-look-ahead contract.
    const completed = payload.values
      .slice(1, MAX_API_BARS + 1)
      .map(validateCandle)
      .reverse();

    if (completed.length < 10) {
      throw new Error("not enough completed candles returned by the provider");
    }

    return completed;
  } finally {
    clearTimeout(timeout);
  }
}

async function handleSignal(request, env) {
  if (request.method !== "GET") {
    return json({ error: "method_not_allowed" }, 405);
  }

  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  const rawTolerance = url.searchParams.get("tolerance");
  const tolerance = rawTolerance == null ? DEFAULT_ZONE_TOLERANCE : finiteNumber(rawTolerance, "tolerance");

  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
    throw new BadRequest("symbol must look like EUR/USD");
  }
  if (!Object.prototype.hasOwnProperty.call(TIMEFRAME_MAP, timeframe)) {
    throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  }
  if (!(tolerance > 0)) {
    throw new BadRequest("tolerance must be > 0");
  }
  if (!env.TWELVE_DATA_API_KEY) {
    return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);
  }

  const candles = await fetchTwelveData(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  const currentPrice = candles[candles.length - 1].close;
  const zones = findZones(candles, tolerance);
  const support = nearestZone(zones, currentPrice, SUPPORT);
  const resistance = nearestZone(zones, currentPrice, RESISTANCE);

  const candidates = [];
  if (support) candidates.push({ direction: LONG, zone: support, result: evaluateSequence(candles, support, timeframe, LONG) });
  if (resistance) candidates.push({ direction: SHORT, zone: resistance, result: evaluateSequence(candles, resistance, timeframe, SHORT) });

  const actionable = candidates.find((candidate) => candidate.result.action === candidate.direction);
  const selected = actionable || candidates[0] || null;
  const result = selected?.result ?? { action: WAIT, state: "APPROACH", reason: "no confirmed support/resistance zones", breakoutState: NO_BREAKOUT };

  return json({
    symbol,
    timeframe,
    signal: result.action,
    state: result.state,
    reason: result.reason,
    price: currentPrice,
    zone: selected?.zone ?? null,
    entry_reference: result.entryReference ?? null,
    stop_reference: selected?.zone && result.action === selected.direction ? stopReference(selected.zone, selected.direction, candles, timeframe) : null,
    breakout_state: result.breakoutState,
    candles_used: candles.length,
    generated_at: new Date().toISOString(),
    execution: "NONE",
  });
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (url.pathname === "/api/signal") {
        return await handleSignal(request, env);
      }
      return env.ASSETS.fetch(request);
    } catch (error) {
      if (error instanceof BadRequest) {
        return json({ error: "bad_request", message: error.message }, 400);
      }
      if (error?.name === "AbortError") {
        return json({ error: "upstream_timeout", message: "market data request timed out" }, 504);
      }
      return json({ error: "upstream_or_internal_error", message: error?.message || "unknown error" }, 502);
    }
  },
};
