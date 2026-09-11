/**
 * Closed-candle feed guard for the Worker realtime path.
 *
 * Mirrors the safety boundary of strategy/feed_integrity.py and
 * strategy/realtime_guard.py. It rejects malformed, misaligned, duplicate,
 * future, and stale observations before strategy evaluation.
 */

const TIMEFRAME_SECONDS = Object.freeze({
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "30m": 1800,
  "1h": 3600,
  "4h": 14400,
  "1D": 86400,
});

const lastEvaluated = new Map();

function parseTime(value) {
  if (value instanceof Date) return value;
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    // MT5 sends Unix epoch seconds. Accept milliseconds too for generic callers.
    const milliseconds = value < 100_000_000_000 ? value * 1000 : value;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  if (typeof value !== "string" || !value.trim()) return null;
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized) ? normalized : `${normalized}Z`;
  const date = new Date(withZone);
  return Number.isNaN(date.getTime()) ? null : date;
}

function validateFeedBatch(candles, timeframe) {
  const duration = TIMEFRAME_SECONDS[timeframe];
  if (!duration) return { ok: false, reason: `unsupported timeframe: ${timeframe}` };
  if (!Array.isArray(candles) || !candles.length) return { ok: false, reason: "empty feed" };

  let previousMs = null;
  for (const candle of candles) {
    const values = [candle.open, candle.high, candle.low, candle.close].map(Number);
    if (values.some((value) => !Number.isFinite(value))) return { ok: false, reason: "non-finite OHLC value" };
    if (candle.high < Math.max(candle.open, candle.close) || candle.low > Math.min(candle.open, candle.close) || candle.high < candle.low) {
      return { ok: false, reason: "invalid OHLC geometry" };
    }
    const time = parseTime(candle.datetime ?? candle.time);
    if (!time) return { ok: false, reason: "bar timestamp must be parseable" };
    const ms = time.getTime();
    if (previousMs !== null) {
      if (ms === previousMs) return { ok: false, reason: "duplicate bar timestamps" };
      if (ms < previousMs) return { ok: false, reason: "bars must be strictly chronological" };
    }
    if (Math.floor(ms / 1000) % duration !== 0) return { ok: false, reason: "bar timestamp is not aligned to timeframe grid" };
    previousMs = ms;
  }
  return { ok: true, reason: "feed integrity passed" };
}

export function validateRealtimeFeed(candles, timeframe, symbol = "", now = new Date(), maxStalenessBars = 2) {
  const integrity = validateFeedBatch(candles, timeframe);
  if (!integrity.ok) return integrity;
  if (!Number.isInteger(maxStalenessBars) || maxStalenessBars < 1) throw new Error("maxStalenessBars must be >= 1");
  const latest = parseTime(candles[candles.length - 1].datetime ?? candles[candles.length - 1].time);
  const reference = now instanceof Date ? now : parseTime(now);
  if (!latest || !reference) return { ok: false, reason: "invalid feed/reference timestamp" };
  const ageSeconds = (reference.getTime() - latest.getTime()) / 1000;
  const maxAge = TIMEFRAME_SECONDS[timeframe] * maxStalenessBars;
  if (ageSeconds < 0) return { ok: false, reason: "latest bar timestamp is in the future", latest_time: latest.toISOString(), age_seconds: ageSeconds };
  if (ageSeconds > maxAge) return { ok: false, reason: "feed is stale", latest_time: latest.toISOString(), age_seconds: ageSeconds };

  const key = `${symbol}:${timeframe}`;
  const previous = lastEvaluated.get(key);
  if (previous !== undefined && latest.getTime() <= previous) {
    return { ok: false, reason: "duplicate or old closed bar", latest_time: latest.toISOString(), age_seconds: ageSeconds };
  }
  return { ok: true, reason: "ok", latest_time: latest.toISOString(), age_seconds: ageSeconds };
}

export function acceptRealtimeFeed(candles, timeframe, symbol = "") {
  const latest = parseTime(candles[candles.length - 1]?.datetime ?? candles[candles.length - 1]?.time);
  if (latest) lastEvaluated.set(`${symbol}:${timeframe}`, latest.getTime());
}

export function resetRealtimeFeedGuard() {
  lastEvaluated.clear();
}
