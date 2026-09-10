// Webaria Pages compatibility endpoint.
// The Worker deployment provides the canonical /api/signal implementation. This
// Pages Function keeps the standalone Pages deployment usable when that Worker
// is not the process serving the site.
//
// Strategy mode here intentionally mirrors the repository's indicator-free
// price-action contract using completed OHLC candles only.
// It is research/paper-only: execution is always NONE.

const CONFIG = Object.freeze({
  "1m": { interval: "1min", seconds: 60 },
  "5m": { interval: "5min", seconds: 300 },
  "15m": { interval: "15min", seconds: 900 },
  "30m": { interval: "30min", seconds: 1800 },
  "1h": { interval: "1h", seconds: 3600 },
  "4h": { interval: "4h", seconds: 14400 },
  "1D": { interval: "1day", seconds: 86400 },
});

const BASE_PRICE = Object.freeze({
  "EUR/USD": 1.08500,
  "GBP/USD": 1.27000,
  "USD/JPY": 147.500,
  "AUD/USD": 0.66000,
  "USD/CAD": 1.35500,
});

const STRATEGY_VERSION = "wiki-price-action-v1";
const SWING_STRENGTH = 2;
const LOOKBACK = 30;
const MIN_TOUCHES = 2;
const MAX_TEST_AGE = 3;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function finite(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${name} is invalid`);
  return number;
}

function validateCandle(raw) {
  const candle = {
    open: finite(raw.open, "open"),
    high: finite(raw.high, "high"),
    low: finite(raw.low, "low"),
    close: finite(raw.close, "close"),
    datetime: String(raw.datetime || ""),
  };
  if (
    candle.high < Math.max(candle.open, candle.close)
    || candle.low > Math.min(candle.open, candle.close)
    || candle.high < candle.low
  ) {
    throw new Error("invalid OHLC relationship");
  }
  return candle;
}

function averageRange(candles, lookback = LOOKBACK) {
  const sample = candles.slice(-lookback);
  if (!sample.length) return 0;
  return sample.reduce((sum, candle) => sum + (candle.high - candle.low), 0) / sample.length;
}

function pressure(candle) {
  const range = candle.high - candle.low;
  if (!(range > 0)) return "NEUTRAL";
  const closePosition = (candle.close - candle.low) / range;
  if (candle.close > candle.open && closePosition >= 0.70) return "BUYING";
  if (candle.close < candle.open && closePosition <= 0.30) return "SELLING";
  return "NEUTRAL";
}

function rejection(candle, direction) {
  const upperWick = candle.high - Math.max(candle.open, candle.close);
  const lowerWick = Math.min(candle.open, candle.close) - candle.low;
  return direction === "LONG"
    ? pressure(candle) === "BUYING" && lowerWick >= upperWick
    : direction === "SHORT"
      ? pressure(candle) === "SELLING" && upperWick >= lowerWick
      : false;
}

function confirmedSwingLows(candles, strength = SWING_STRENGTH) {
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
    if (unique) result.push({ index: i, price: low });
  }
  return result;
}

function confirmedSwingHighs(candles, strength = SWING_STRENGTH) {
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
    if (unique) result.push({ index: i, price: high });
  }
  return result;
}

function clusterSwings(swings, tolerance) {
  if (!(tolerance > 0)) return [];
  const clusters = [];
  for (const swing of [...swings].sort((a, b) => a.price - b.price)) {
    const last = clusters.at(-1);
    if (!last || swing.price - last[0].price > tolerance) clusters.push([swing]);
    else last.push(swing);
  }
  return clusters;
}

function buildZones(swings, kind, tolerance) {
  return clusterSwings(swings, tolerance)
    .filter((cluster) => cluster.length >= MIN_TOUCHES)
    .map((cluster) => {
      const prices = cluster.map((item) => item.price);
      const low = Math.min(...prices) - tolerance;
      const high = Math.max(...prices) + tolerance;
      return {
        kind,
        low,
        high,
        center: (low + high) / 2,
        touches: cluster.length,
        latest_index: Math.max(...cluster.map((item) => item.index)),
      };
    });
}

function marketStructure(candles) {
  const highs = confirmedSwingHighs(candles);
  const lows = confirmedSwingLows(candles);
  let bias = "UNKNOWN";
  if (highs.length >= 2 && lows.length >= 2) {
    const higherHigh = highs.at(-1).price > highs.at(-2).price;
    const higherLow = lows.at(-1).price > lows.at(-2).price;
    const lowerHigh = highs.at(-1).price < highs.at(-2).price;
    const lowerLow = lows.at(-1).price < lows.at(-2).price;
    if (higherHigh && higherLow) bias = "BULLISH";
    else if (lowerHigh && lowerLow) bias = "BEARISH";
    else bias = "RANGE";
  }
  return { bias, highs, lows };
}

function nearestZone(zones, price, kind) {
  const candidates = zones.filter((zone) => (
    kind === "SUPPORT" ? zone.center <= price : zone.center >= price
  ));
  if (!candidates.length) return null;
  return candidates.sort((a, b) => Math.abs(a.center - price) - Math.abs(b.center - price))[0];
}

function zoneTouches(candle, zone) {
  return candle.low <= zone.high && candle.high >= zone.low;
}

function evaluateDirection(candles, zone, direction, confirmationBuffer) {
  const currentIndex = candles.length - 1;
  const current = candles[currentIndex];
  const start = Math.max(0, currentIndex - MAX_TEST_AGE);

  for (let i = currentIndex - 1; i >= start; i -= 1) {
    const test = candles[i];
    if (!zoneTouches(test, zone)) continue;

    if (direction === "LONG") {
      const pierced = test.low < zone.low;
      const decisiveBreak = test.close < zone.low - confirmationBuffer;
      const fakeBreak = pierced && test.close > zone.high;
      if (decisiveBreak) return { state: "BROKEN", breakoutState: "TRUE_BREAKOUT", reason: "support closed decisively below the zone" };

      const rejected = !pierced && test.close > zone.high && rejection(test, "LONG");
      if (!fakeBreak && !rejected) continue;
      if (pressure(current) !== "BUYING") {
        return { state: "CONFIRM", breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT", reason: "support reacted but confirmation candle is not strongly bullish" };
      }
      if (current.close <= zone.high) {
        return { state: "CONFIRM", breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT", reason: "buyers have not confirmed a close above support" };
      }
      return {
        state: "CONFIRM",
        breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT",
        action: "LONG",
        reason: fakeBreak ? "fake support break followed by bullish confirmation" : "support rejection followed by bullish confirmation",
        entryReference: current.close,
      };
    }

    const pierced = test.high > zone.high;
    const decisiveBreak = test.close > zone.high + confirmationBuffer;
    const fakeBreak = pierced && test.close < zone.low;
    if (decisiveBreak) return { state: "BROKEN", breakoutState: "TRUE_BREAKOUT", reason: "resistance closed decisively above the zone" };

    const rejected = !pierced && test.close < zone.low && rejection(test, "SHORT");
    if (!fakeBreak && !rejected) continue;
    if (pressure(current) !== "SELLING") {
      return { state: "CONFIRM", breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT", reason: "resistance reacted but confirmation candle is not strongly bearish" };
    }
    if (current.close >= zone.low) {
      return { state: "CONFIRM", breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT", reason: "sellers have not confirmed a close below resistance" };
    }
    return {
      state: "CONFIRM",
      breakoutState: fakeBreak ? "FAKE_BREAKOUT" : "NO_BREAKOUT",
      action: "SHORT",
      reason: fakeBreak ? "fake resistance break followed by bearish confirmation" : "resistance rejection followed by bearish confirmation",
      entryReference: current.close,
    };
  }

  return { state: "APPROACH", breakoutState: "NO_BREAKOUT", reason: "no complete test-and-confirmation sequence" };
}

function scoreSetup(direction, zone, structureBias, breakoutState, confirmationStrength) {
  const structure = (direction === "LONG" && structureBias === "BULLISH") || (direction === "SHORT" && structureBias === "BEARISH") ? 20 : 0;
  const zoneScore = Math.min(25, zone.touches * 5);
  const breakout = breakoutState === "FAKE_BREAKOUT" ? 25 : breakoutState === "NO_BREAKOUT" ? 20 : 0;
  const total = zoneScore + structure + breakout + confirmationStrength;
  return {
    total,
    zone: zoneScore,
    structure,
    breakout,
    confirmation: confirmationStrength,
  };
}

export function evaluatePriceAction(candles, timeframe) {
  if (!Object.prototype.hasOwnProperty.call(CONFIG, timeframe)) throw new Error(`unsupported timeframe: ${timeframe}`);
  if (!Array.isArray(candles) || candles.length < 20) {
    return {
      signal: "WAIT",
      state: "APPROACH",
      reason: "not enough completed candles",
      structure_bias: "UNKNOWN",
      breakout_state: "NO_BREAKOUT",
      score: null,
      zone: null,
      entry_reference: null,
      stop_reference: null,
    };
  }

  const completed = candles.slice(-Math.max(LOOKBACK, 20));
  const structure = marketStructure(completed);
  const avgRange = averageRange(completed);
  const tolerance = Math.max(avgRange * 0.50, completed.at(-1).close * 0.00005);
  const confirmationBuffer = Math.max(avgRange * 0.20, tolerance * 0.20);
  const supports = buildZones(structure.lows, "SUPPORT", tolerance);
  const resistances = buildZones(structure.highs, "RESISTANCE", tolerance);
  const price = completed.at(-1).close;

  const candidates = [];
  if (structure.bias === "BULLISH") {
    const zone = nearestZone(supports, price, "SUPPORT");
    if (zone) candidates.push({ direction: "LONG", zone, result: evaluateDirection(completed, zone, "LONG", confirmationBuffer) });
  }
  if (structure.bias === "BEARISH") {
    const zone = nearestZone(resistances, price, "RESISTANCE");
    if (zone) candidates.push({ direction: "SHORT", zone, result: evaluateDirection(completed, zone, "SHORT", confirmationBuffer) });
  }

  for (const candidate of candidates) {
    if (candidate.result.action !== candidate.direction) continue;
    const confirmationStrength = pressure(completed.at(-1)) === (candidate.direction === "LONG" ? "BUYING" : "SELLING") ? 20 : 0;
    const score = scoreSetup(candidate.direction, candidate.zone, structure.bias, candidate.result.breakoutState, confirmationStrength);
    if (score.total < 60) continue;
    const stopReference = candidate.direction === "LONG"
      ? candidate.zone.low - confirmationBuffer
      : candidate.zone.high + confirmationBuffer;
    return {
      signal: candidate.direction,
      state: "CONFIRM",
      reason: candidate.result.reason,
      structure_bias: structure.bias,
      breakout_state: candidate.result.breakoutState,
      score: score.total,
      score_breakdown: score,
      zone: candidate.zone,
      entry_reference: candidate.result.entryReference,
      stop_reference: stopReference,
      strategy_version: STRATEGY_VERSION,
    };
  }

  const directional = candidates[0];
  return {
    signal: "WAIT",
    state: directional?.result?.state || "APPROACH",
    reason: directional?.result?.reason || "structure and zone conditions are incomplete",
    structure_bias: structure.bias,
    breakout_state: directional?.result?.breakoutState || "NO_BREAKOUT",
    score: directional?.zone ? scoreSetup(directional.direction, directional.zone, structure.bias, directional.result.breakoutState, pressure(completed.at(-1)) === (directional.direction === "LONG" ? "BUYING" : "SELLING") ? 20 : 0).total : null,
    zone: directional?.zone || null,
    entry_reference: null,
    stop_reference: null,
    strategy_version: STRATEGY_VERSION,
  };
}

function fallbackCandles(symbol, timeframe, count = 100) {
  const step = CONFIG[timeframe].seconds;
  const base = BASE_PRICE[symbol] ?? 1.00000;
  const now = Math.floor(Date.now() / 1000 / step) * step;
  let price = base;
  const candles = [];

  // Deterministic fallback: same request bucket produces a stable chart
  // instead of a new random market on every poll.
  for (let i = count; i > 0; i -= 1) {
    const bucket = Math.floor((now / step) - i);
    const wave = Math.sin(bucket * 0.73) * 0.00035;
    const drift = Math.cos(bucket * 0.17) * 0.00010;
    const direction = wave + drift;
    const open = price;
    const close = open + direction;
    const wick = Math.max(Math.abs(direction) * 0.45, base * 0.00015);
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick;
    candles.push({
      datetime: new Date((now - i * step) * 1000).toISOString(),
      open: Number(open.toFixed(6)),
      high: Number(high.toFixed(6)),
      low: Number(low.toFixed(6)),
      close: Number(close.toFixed(6)),
    });
    price = close;
  }
  return candles;
}

async function fetchRealCandles(symbol, timeframe, apiKey) {
  const config = CONFIG[timeframe];
  const url = new URL("https://api.twelvedata.com/time_series");
  url.searchParams.set("symbol", symbol.replace("/", ""));
  url.searchParams.set("interval", config.interval);
  url.searchParams.set("outputsize", "100");
  url.searchParams.set("timezone", "UTC");
  url.searchParams.set("apikey", apiKey);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`provider HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.status === "error" || !Array.isArray(payload.values)) {
      throw new Error(payload.message || "invalid provider response");
    }

    const candles = payload.values
      .slice(1, 101) // never use the currently forming candle for strategy history
      .map(validateCandle)
      .reverse();
    if (candles.length < 20) throw new Error("not enough completed candles");
    return { candles, source: "twelve-data" };
  } finally {
    clearTimeout(timer);
  }
}

export async function onRequestGet(context) {
  try {
    const url = new URL(context.request.url);
    const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
    const timeframe = (url.searchParams.get("timeframe") || "15m").trim();

    if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
      return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);
    }
    if (!Object.prototype.hasOwnProperty.call(CONFIG, timeframe)) {
      return json({ error: "bad_request", message: `unsupported timeframe: ${timeframe}` }, 400);
    }

    let candles;
    let source;
    if (context.env?.TWELVE_DATA_API_KEY) {
      try {
        ({ candles, source } = await fetchRealCandles(symbol, timeframe, context.env.TWELVE_DATA_API_KEY));
      } catch (_) {
        candles = fallbackCandles(symbol, timeframe);
        source = "pages-fallback";
      }
    } else {
      candles = fallbackCandles(symbol, timeframe);
      source = "pages-fallback";
    }

    const signal = evaluatePriceAction(candles, timeframe);
    return json({
      symbol,
      timeframe,
      price: candles.at(-1)?.close ?? null,
      ...signal,
      candles,
      candles_used: candles.length,
      source,
      execution: "NONE",
      generated_at: new Date().toISOString(),
    });
  } catch (error) {
    return json({ error: "internal_error", message: error?.message || "unknown error" }, 500);
  }
}
