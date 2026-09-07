// functions/api/market.js
//
// Cloudflare Pages Function — runs on the server every time the page calls
// fetch('/api/market'). Right now it returns realistic MOCK candle data so
// the chart and signal panel have something to render immediately.
//
// ── NEXT STEPS (in order) ───────────────────────────────────────────────
// 1. Replace `getCandles()` with a real fetch() to a forex OHLC data
//    provider (e.g. one that gives M15 candles for EURUSD). Store the API
//    key as a Cloudflare Pages environment variable (Settings → Environment
//    variables) and read it here via `env.FOREX_API_KEY` — never hardcode
//    a key in this file.
// 2. Replace `computeSignal()` with the real strategy logic ported from
//    the Ariatrading Python repo (structural bias, zone quality, candle
//    pressure, setup scoring).
// ──────────────────────────────────────────────────────────────────────

const SYMBOL = 'EUR/USD';
const TIMEFRAME = 'M15';
const CANDLE_COUNT = 120;

export async function onRequestGet(context) {
  // const { env } = context; // will hold FOREX_API_KEY etc. once real data is wired in

  const candles = getCandles(CANDLE_COUNT);
  const lastClose = candles[candles.length - 1].close;
  const firstClose = candles[0].close;
  const changePct = ((lastClose - firstClose) / firstClose) * 100;

  const signal = computeSignal(candles);

  const payload = {
    symbol: SYMBOL,
    timeframe: TIMEFRAME,
    price: lastClose,
    changePct,
    candles,
    signal,
    updatedAt: Date.now(),
  };

  return new Response(JSON.stringify(payload), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    },
  });
}

// ── MOCK DATA (replace with real API call) ──────────────────────────────
function getCandles(count) {
  const candles = [];
  let price = 1.0850;
  const now = Math.floor(Date.now() / 1000);
  const stepSeconds = 15 * 60; // M15

  for (let i = count; i > 0; i--) {
    const time = now - i * stepSeconds;
    const open = price;
    const drift = (Math.random() - 0.5) * 0.0018;
    const close = +(open + drift).toFixed(5);
    const high = +(Math.max(open, close) + Math.random() * 0.0008).toFixed(5);
    const low = +(Math.min(open, close) - Math.random() * 0.0008).toFixed(5);

    candles.push({ time, open, high, low, close });
    price = close;
  }

  return candles;
}

// ── MOCK SIGNAL (replace with the real Ariatrading scoring engine) ─────
function computeSignal(candles) {
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const bullish = last.close > prev.close;

  // Placeholder scoring — swap for the real setup-score logic.
  const score = Math.round(40 + Math.random() * 40);

  let direction = 'WAIT';
  let reason = 'โครงสร้างยังไม่ชัดเจนพอ รอสัญญาณที่แข็งแรงกว่านี้';

  if (score >= 70) {
    direction = bullish ? 'LONG' : 'SHORT';
    reason = bullish
      ? 'แนวโน้มระยะสั้นเป็นขาขึ้น และราคาหลุดโซนแนวต้านล่าสุด'
      : 'แนวโน้มระยะสั้นเป็นขาลง และราคาหลุดโซนแนวรับล่าสุด';
  }

  return { direction, score, reason };
}
