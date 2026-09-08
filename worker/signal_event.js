/**
 * Deterministic identity for a realtime signal event.
 *
 * The ID is derived only from stable decision inputs, never generated_at, so
 * repeated polling of the same closed candle produces the same event_id.
 * This is a deduplication key, not an authorization or security token.
 */

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function canonicalSignalEvent(payload) {
  const zone = payload.zone
    ? [payload.zone.kind, payload.zone.low, payload.zone.high, payload.zone.touches]
    : null;
  return JSON.stringify([
    payload.symbol,
    payload.timeframe,
    payload.bar_time ?? payload.candles?.at(-1)?.datetime ?? payload.candles?.at(-1)?.time ?? null,
    payload.signal,
    payload.state,
    payload.breakout_state,
    payload.price,
    payload.entry_reference,
    payload.stop_reference,
    payload.structure_bias,
    payload.score?.total ?? null,
    zone,
  ]);
}

export async function buildSignalEventId(payload) {
  const canonical = canonicalSignalEvent(payload);
  const digest = await sha256Hex(canonical);
  return `sig_${digest.slice(0, 32)}`;
}
