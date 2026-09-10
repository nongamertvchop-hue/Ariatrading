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
