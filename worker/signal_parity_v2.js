/**
 * Worker signal adapter that follows the Python realtime engine contract.
 *
 * The low-level primitives live in signal_parity.js. This adapter fixes the
 * orchestration semantics: empty support/resistance sets are valid WAIT states,
 * every candidate zone is evaluated, history excludes the current candle for
 * zone/structure context, and zone centers follow PriceZone.center exactly.
 */

import {
  LONG,
  SHORT,
  WAIT,
  SUPPORT,
  RESISTANCE,
  NO_BREAKOUT,
  TIMEFRAME_CONFIG,
  BadRequest,
  adaptiveZoneTolerance,
  evaluateSequence,
  analyzeMarketStructure,
  findSupportZones,
  findResistanceZones,
  scoreSetup,
  fetchTwelveData,
  validateCandle,
} from "./signal_parity.js";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function bestSignal(candidates, direction, timeframe, emptyReason) {
  if (!candidates.length) return { action: WAIT, reason: emptyReason, timeframe };
  return [...candidates].sort((a, b) => {
    const aKey = [a.result.action === direction ? 1 : 0, a.score?.total ?? -1, a.result.entryReference ?? 0];
    const bKey = [b.result.action === direction ? 1 : 0, b.score?.total ?? -1, b.result.entryReference ?? 0];
    for (let i = 0; i < aKey.length; i += 1) {
      if (aKey[i] !== bKey[i]) return bKey[i] - aKey[i];
    }
    return 0;
  })[0];
}

function selectSignal(longSignal, shortSignal, timeframe) {
  const longOk = longSignal.action === LONG;
  const shortOk = shortSignal.action === SHORT;
  if (longOk && !shortOk) return longSignal;
  if (shortOk && !longOk) return shortSignal;
  if (longOk && shortOk) {
    const longScore = longSignal.score?.total ?? -1;
    const shortScore = shortSignal.score?.total ?? -1;
    if (longScore !== shortScore) return longScore > shortScore ? longSignal : shortSignal;
  }
  return { action: WAIT, reason: "no unambiguous realtime setup", timeframe };
}

function nearestSupport(price, zones) {
  const candidates = zones.filter((zone) => zone.center <= price || (zone.low <= price && price <= zone.high));
  return candidates.sort((a, b) => {
    const ad = a.low <= price && price <= a.high ? 0 : price - a.high;
    const bd = b.low <= price && price <= b.high ? 0 : price - b.high;
    return ad !== bd ? ad - bd : b.touches - a.touches;
  })[0] ?? null;
}

function nearestResistance(price, zones) {
  const candidates = zones.filter((zone) => zone.center >= price || (zone.low <= price && price <= zone.high));
  return candidates.sort((a, b) => {
    const ad = a.low <= price && price <= a.high ? 0 : a.low - price;
    const bd = b.low <= price && price <= b.high ? 0 : b.low - price;
    return ad !== bd ? ad - bd : b.touches - a.touches;
  })[0] ?? null;
}

function stopReference(zone, direction, history, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  const range = history.slice(-config.lookback).reduce((sum, candle) => sum + (candle.high - candle.low), 0) / Math.min(history.length, config.lookback);
  const buffer = Math.max(config.minZoneDistance * 0.5, range * config.confirmationMultiplier);
  return direction === LONG ? zone.low - buffer : zone.high + buffer;
}

export function evaluateRealtimeSignalParity(rawCandles, timeframe) {
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  const candles = rawCandles.map(validateCandle);
  if (candles.length < 5) throw new BadRequest("not enough completed candles for evaluation");

  const history = candles.slice(0, -1);
  const tolerance = adaptiveZoneTolerance(history, timeframe);
  const supports = findSupportZones(history, tolerance);
  const resistances = findResistanceZones(history, tolerance);
  const structure = analyzeMarketStructure(history);

  const longCandidates = supports.map((zone) => {
    const result = evaluateSequence(candles, zone, timeframe, LONG, 3);
    return { direction: LONG, zone, result, score: result.action === LONG ? scoreSetup(LONG, zone.touches, structure.bias, result.breakoutState, 20) : null };
  });
  const shortCandidates = resistances.map((zone) => {
    const result = evaluateSequence(candles, zone, timeframe, SHORT, 3);
    return { direction: SHORT, zone, result, score: result.action === SHORT ? scoreSetup(SHORT, zone.touches, structure.bias, result.breakoutState, 20) : null };
  });

  const longSignal = bestSignal(longCandidates, LONG, timeframe, "no support zone");
  const shortSignal = bestSignal(shortCandidates, SHORT, timeframe, "no resistance zone");
  const selected = selectSignal(longSignal, shortSignal, timeframe);
  const currentPrice = candles[candles.length - 1].close;
  const selectedScore = selected.action === LONG || selected.action === SHORT ? selected.score ?? null : null;

  return {
    signal: selected.action,
    state: selected.result?.state ?? "APPROACH",
    reason: selected.reason,
    price: currentPrice,
    structure_bias: structure.bias,
    zone: selected.zone ?? null,
    entry_reference: selected.result?.entryReference ?? null,
    stop_reference: selected.zone && selected.action !== WAIT ? stopReference(selected.zone, selected.action, history, timeframe) : null,
    breakout_state: selected.result?.breakoutState ?? NO_BREAKOUT,
    score: selectedScore,
    support: nearestSupport(currentPrice, supports),
    resistance: nearestResistance(currentPrice, resistances),
    candles,
    candles_used: candles.length,
  };
}

export async function handleSignalParityV2(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);

  const candles = await fetchTwelveData(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  const result = evaluateRealtimeSignalParity(candles, timeframe);
  return json({ symbol, timeframe, ...result, generated_at: new Date().toISOString(), execution: "NONE" });
}
