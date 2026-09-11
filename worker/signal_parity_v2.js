/**
 * Worker signal adapter that follows the Python realtime engine contract.
 *
 * The low-level primitives live in signal_parity.js. Market candles are read
 * from the MT5 Durable Object so /api/market and /api/signal cannot silently
 * analyze different price feeds.
 */

import {
  LONG,
  SHORT,
  WAIT,
  NO_BREAKOUT,
  TIMEFRAME_CONFIG,
  BadRequest,
  adaptiveZoneTolerance,
  evaluateSequence,
  analyzeMarketStructure,
  findSupportZones,
  findResistanceZones,
  scoreSetup,
  validateCandle,
} from "./signal_parity.js";
import { forecast, supervise } from "./forecast_parity.js";
import { validateRealtimeFeed, acceptRealtimeFeed } from "./realtime_feed_guard.js";
import { buildSignalEventId } from "./signal_event.js";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function decorateCandidate(candidate, structureBias) {
  return {
    ...candidate.result,
    zone: candidate.zone ?? null,
    score: candidate.score ?? null,
    protection: candidate.result.protection ?? "SAFE",
    structureBias: candidate.result.structureBias ?? structureBias,
  };
}

function bestSignal(candidates, direction, timeframe, emptyReason, structureBias) {
  if (!candidates.length) return { action: WAIT, reason: emptyReason, timeframe, protection: "SAFE", breakoutState: NO_BREAKOUT, structureBias };
  const directional = candidates.filter((candidate) => candidate.result.action === direction);
  if (!directional.length) return decorateCandidate(candidates[0], structureBias);
  return [...directional].sort((a, b) => (b.score?.total ?? -1) - (a.score?.total ?? -1))[0] && decorateCandidate([...directional].sort((a, b) => (b.score?.total ?? -1) - (a.score?.total ?? -1))[0], structureBias);
}

function selectSignal(longSignal, shortSignal, timeframe, structureBias) {
  if (longSignal.action !== WAIT && shortSignal.action === WAIT) return longSignal;
  if (shortSignal.action !== WAIT && longSignal.action === WAIT) return shortSignal;
  if (longSignal.action === WAIT && shortSignal.action === WAIT) return { action: WAIT, reason: "no directional setup", timeframe, protection: "SAFE", breakoutState: NO_BREAKOUT, structureBias };
  const longScore = longSignal.score?.total ?? -1;
  const shortScore = shortSignal.score?.total ?? -1;
  return longScore > shortScore ? longSignal : shortSignal;
}

function nearestSupport(price, zones) {
  return zones.filter((zone) => zone.center <= price).sort((a, b) => (price - a.center) - (price - b.center))[0] ?? null;
}

function nearestResistance(price, zones) {
  return zones.filter((zone) => zone.center >= price).sort((a, b) => (a.center - price) - (b.center - price))[0] ?? null;
}

function stopReference(zone, direction, history, timeframe) {
  const config = TIMEFRAME_CONFIG[timeframe];
  const sample = history.slice(-config.lookback);
  const range = sample.reduce((sum, candle) => sum + (candle.high - candle.low), 0) / Math.min(history.length, config.lookback);
  const buffer = Math.max(config.minZoneDistance * 0.5, range * config.confirmationMultiplier);
  return direction === LONG ? zone.low - buffer : zone.high + buffer;
}

export function evaluateRealtimeSignalParity(rawCandles, timeframe, minForecastConfidence = 0.45) {
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
  const longSignal = bestSignal(longCandidates, LONG, timeframe, "no support zone", structure.bias);
  const shortSignal = bestSignal(shortCandidates, SHORT, timeframe, "no resistance zone", structure.bias);
  const strategySignal = selectSignal(longSignal, shortSignal, timeframe, structure.bias);
  const currentPrice = candles[candles.length - 1].close;
  const support = nearestSupport(currentPrice, supports);
  const resistance = nearestResistance(currentPrice, resistances);
  const forecastResult = forecast(candles, [1, 3, 5], support, resistance);
  const supervisor = supervise(strategySignal, forecastResult, null, minForecastConfidence);
  let finalSignal = strategySignal;
  if (supervisor.action !== "ALLOW") {
    finalSignal = { ...strategySignal, action: WAIT, reason: `realtime supervisor: ${supervisor.reasons.join("; ")}`, protection: "BLOCKED" };
  }
  const selectedScore = strategySignal.action === LONG || strategySignal.action === SHORT ? strategySignal.score ?? null : null;
  const latestRawCandle = rawCandles[rawCandles.length - 1];
  return {
    signal: finalSignal.action,
    state: finalSignal.state ?? "APPROACH",
    reason: finalSignal.reason,
    price: currentPrice,
    bar_time: latestRawCandle?.datetime ?? latestRawCandle?.time ?? null,
    structure_bias: finalSignal.structureBias ?? structure.bias,
    zone: finalSignal.zone ?? null,
    entry_reference: finalSignal.entryReference ?? null,
    stop_reference: finalSignal.zone && finalSignal.action !== WAIT ? stopReference(finalSignal.zone, finalSignal.action, history, timeframe) : null,
    breakout_state: finalSignal.breakoutState ?? NO_BREAKOUT,
    protection: finalSignal.protection ?? "SAFE",
    score: selectedScore,
    support,
    resistance,
    forecast: forecastResult,
    supervisor,
    candles,
    candles_used: candles.length,
  };
}

async function fetchMt5Market(env, symbol, timeframe) {
  if (!env?.MT5_MARKET) return { response: json({ error: "mt5_market_unavailable", message: "MT5 market binding is not configured", source: "unavailable", execution: "NONE" }, 503) };
  const id = env.MT5_MARKET.idFromName("market");
  const target = new URL(`https://mt5.internal/market?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`);
  const response = await env.MT5_MARKET.get(id).fetch(new Request(target.toString(), { method: "GET" }));
  return { response };
}

export async function handleSignalParityV2(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);

  const market = await fetchMt5Market(env, symbol, timeframe);
  if (!market.response.ok) return market.response;
  const payload = await market.response.json();
  if (payload.source !== "mt5" || !Array.isArray(payload.candles) || !/^[0-9a-f]{64}$/.test(payload.market_fingerprint || "")) {
    return json({ error: "mt5_market_contract_rejected", message: "MT5 market contract or snapshot fingerprint rejected", source: "unavailable", execution: "NONE" }, 503);
  }

  const candles = payload.candles.map((candle) => ({
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    datetime: new Date(Number(candle.time) * 1000).toISOString(),
  }));
  const quality = validateRealtimeFeed(candles, timeframe, symbol);
  if (!quality.ok) {
    if (quality.reason === "duplicate or old closed bar") {
      return json({ symbol, timeframe, signal: WAIT, state: "NO_UPDATE", reason: quality.reason, data_quality: quality, no_update: true, source: "mt5", market_fingerprint: payload.market_fingerprint, execution: "NONE" });
    }
    return json({ error: "realtime_data_rejected", message: quality.reason, data_quality: quality, market_fingerprint: payload.market_fingerprint, source: "mt5", execution: "NONE" }, 503);
  }

  const result = evaluateRealtimeSignalParity(candles, timeframe);
  const response = { symbol, timeframe, ...result, price: Number(payload.price), live_candle: payload.live_candle ?? null, source: "mt5", market_fingerprint: payload.market_fingerprint, data_quality: { ...quality, broker_age_seconds: payload.data_quality?.age_seconds ?? null }, generated_at: new Date().toISOString(), execution: "NONE" };
  response.event_id = await buildSignalEventId(response);
  acceptRealtimeFeed(candles, timeframe, symbol);
  return json(response);
}
