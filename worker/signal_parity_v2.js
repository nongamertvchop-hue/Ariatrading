/**
 * Worker signal adapter that follows the Python realtime engine contract.
 *
 * The low-level primitives live in signal_parity.js. This adapter keeps the
 * orchestration semantics aligned with strategy/realtime.py: empty
 * support/resistance sets are valid WAIT states, all candidate zones are
 * evaluated, history excludes the current candle for zone/structure context,
 * and zone selection uses PriceZone.center semantics.
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
  fetchTwelveData,
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

function bestSignal(candidates, direction, timeframe, emptyReason) {
  if (!candidates.length) {
    return { action: WAIT, reason: emptyReason, timeframe, protection: "SAFE", breakoutState: NO_BREAKOUT };
  }

  const directional = candidates.filter((candidate) => candidate.result.action === direction);
  if (!directional.length) {
    // Match Python RealtimeMonitor._best_signal(): preserve the first evaluated
    // WAIT result when zones exist so diagnostics do not collapse into "no zone".
    return candidates[0].result;
  }

  return [...directional].sort((a, b) => {
    const aScore = a.score?.total ?? -1;
    const bScore = b.score?.total ?? -1;
    return bScore - aScore;
  })[0].result;
}

function selectSignal(longSignal, shortSignal, timeframe) {
  if (longSignal.action !== WAIT && shortSignal.action === WAIT) return longSignal;
  if (shortSignal.action !== WAIT && longSignal.action === WAIT) return shortSignal;
  if (longSignal.action === WAIT && shortSignal.action === WAIT) {
    return { action: WAIT, reason: "no directional setup", timeframe, protection: "SAFE", breakoutState: NO_BREAKOUT };
  }

  // Python uses `>` and therefore resolves an exact score tie in favor of
  // the short-side candidate. Keep that deterministic rule across runtimes.
  const longScore = longSignal.score?.total ?? -1;
  const shortScore = shortSignal.score?.total ?? -1;
  return longScore > shortScore ? longSignal : shortSignal;
}

function nearestSupport(price, zones) {
  const candidates = zones.filter((zone) => zone.center <= price);
  return candidates.sort((a, b) => (price - a.center) - (price - b.center))[0] ?? null;
}

function nearestResistance(price, zones) {
  const candidates = zones.filter((zone) => zone.center >= price);
  return candidates.sort((a, b) => (a.center - price) - (b.center - price))[0] ?? null;
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

  const longSignal = bestSignal(longCandidates, LONG, timeframe, "no support zone");
  const shortSignal = bestSignal(shortCandidates, SHORT, timeframe, "no resistance zone");
  const strategySignal = selectSignal(longSignal, shortSignal, timeframe);
  const currentPrice = candles[candles.length - 1].close;
  const support = nearestSupport(currentPrice, supports);
  const resistance = nearestResistance(currentPrice, resistances);
  const forecastResult = forecast(candles, [1, 3, 5], support, resistance);
  const supervisor = supervise(strategySignal, forecastResult, null, minForecastConfidence);

  let finalSignal = strategySignal;
  if (supervisor.action !== "ALLOW") {
    // Match strategy/realtime.py: a blocked strategy decision becomes WAIT and
    // exposes the supervisor's reason in the final signal for operators.
    finalSignal = {
      ...strategySignal,
      action: WAIT,
      reason: `realtime supervisor: ${supervisor.reasons.join("; ")}`,
      protection: "BLOCKED",
    };
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

export async function handleSignalParityV2(request, env) {
  if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new BadRequest("symbol must look like EUR/USD");
  if (!TIMEFRAME_CONFIG[timeframe]) throw new BadRequest(`unsupported timeframe: ${timeframe}`);
  if (!env.TWELVE_DATA_API_KEY) return json({ error: "server_not_configured", message: "TWELVE_DATA_API_KEY secret is not configured" }, 503);

  const candles = await fetchTwelveData(symbol, timeframe, env.TWELVE_DATA_API_KEY);
  const quality = validateRealtimeFeed(candles, timeframe, symbol);
  if (!quality.ok) {
    if (quality.reason === "duplicate or old closed bar") {
      return json({
        symbol,
        timeframe,
        signal: WAIT,
        state: "NO_UPDATE",
        reason: quality.reason,
        data_quality: quality,
        no_update: true,
        execution: "NONE",
      });
    }
    return json({ error: "realtime_data_rejected", message: quality.reason, data_quality: quality }, 503);
  }

  const result = evaluateRealtimeSignalParity(candles, timeframe);
  const response = { symbol, timeframe, ...result, data_quality: quality, generated_at: new Date().toISOString(), execution: "NONE" };
  response.event_id = await buildSignalEventId(response);
  acceptRealtimeFeed(candles, timeframe, symbol);
  return json(response);
}