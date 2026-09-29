const TIMEFRAME_SECONDS = Object.freeze({"1m":60,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1D":86400});
const MAX_CANDLES = 500;
const MAX_AGE_SECONDS = 90;
const MAX_INGEST_BYTES = 256 * 1024;
const MARKET_CONTRACT_VERSION = "mt5-market-v6";

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type":"application/json; charset=utf-8", "cache-control":"no-store", "x-webaria-market-contract": MARKET_CONTRACT_VERSION, ...extraHeaders } });
}
function key(symbol, timeframe) { return `${symbol}:${timeframe}`; }
const RUNTIME_STATES = new Set(["READY","RUNNING","PAUSE","STOP","EMERGENCY_STOP","STOPPED","ERROR"]);
const MAX_RUNTIME_STATUS_FIELDS = 16;
function validateRuntimeStatus(raw) {
  if (raw == null) return null;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("invalid runtime_status");
  const clean = {};
  const stringFields = ["runtime_state","reason","mode","timeframe","control_state","updated_at"];
  for (const field of stringFields) {
    if (raw[field] != null) {
      const value = String(raw[field]).slice(0, 300);
      if (field === "runtime_state" && value && !RUNTIME_STATES.has(value.toUpperCase())) throw new Error("invalid runtime_state");
      if (field === "mode" && value && value.toUpperCase() !== "DEMO") throw new Error("runtime_status must be DEMO");
      clean[field] = value;
    }
  }
  if (Array.isArray(raw.symbols)) clean.symbols = raw.symbols.slice(0, 16).map(value => String(value).toUpperCase().slice(0, 32));
  for (const field of ["processed","control_generation"]) {
    if (raw[field] != null) {
      const value = Number(raw[field]);
      if (!Number.isInteger(value) || value < 0) throw new Error("invalid runtime_status " + field);
      clean[field] = value;
    }
  }
  if (Object.keys(clean).length > MAX_RUNTIME_STATUS_FIELDS) throw new Error("runtime_status contains too many fields");
  return Object.keys(clean).length ? clean : null;
}

function validateCandle(raw) {
  const time=Number(raw?.time), open=Number(raw?.open), high=Number(raw?.high), low=Number(raw?.low), close=Number(raw?.close);
  if (!Number.isInteger(time)||time<=0) throw new Error("invalid candle time");
  if (![open,high,low,close].every(Number.isFinite)) throw new Error("invalid candle OHLC");
  if (high<Math.max(open,close)||low>Math.min(open,close)||high<low) throw new Error("invalid candle OHLC relationship");
  return {time,open,high,low,close};
}
function assertCompletedChronology(candles) {
  for (let i=1;i<candles.length;i+=1) {
    if (candles[i].time<=candles[i-1].time) throw new Error("completed candles must be strictly chronological and unique");
  }
}
function assertCompletedCandleSeparation(candles, liveCandle) {
  if (!liveCandle) return;
  if (candles.some(c => c.time === liveCandle.time)) throw new Error("live candle must not be duplicated in completed candles");
  if (candles.length && liveCandle.time <= candles.at(-1).time) throw new Error("live candle must be newer than the latest completed candle");
}
function canonicalPrice(value) {
  const number=Number(value);
  if(!Number.isFinite(number)) throw new Error("non-finite price in fingerprint");
  return number.toFixed(12);
}
function canonicalCompletedPayload(symbol, timeframe, candles) {
  const lines=[`${symbol}\n${timeframe}`];
  for(const candle of candles) lines.push(`${Number(candle.time)}|${canonicalPrice(candle.open)}|${canonicalPrice(candle.high)}|${canonicalPrice(candle.low)}|${canonicalPrice(candle.close)}`);
  return lines.join("\n");
}
async function completedFingerprint(symbol, timeframe, candles) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonicalCompletedPayload(symbol,timeframe,candles)));
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2,"0")).join("");
}
function validatePayload(payload) {
  const symbol=String(payload?.symbol||"").trim().toUpperCase(), timeframe=String(payload?.timeframe||"").trim();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new Error("invalid symbol");
  if (!Object.prototype.hasOwnProperty.call(TIMEFRAME_SECONDS,timeframe)) throw new Error("invalid timeframe");
  const candles=Array.isArray(payload?.candles)?payload.candles:[];
  if(candles.length>MAX_CANDLES) throw new Error("too many candles");
  const normalized=candles.map(c=>validateCandle(c));
  assertCompletedChronology(normalized);
  const liveCandle=payload?.live_candle?validateCandle(payload.live_candle):null;
  assertCompletedCandleSeparation(normalized, liveCandle);
  const receivedAt=Number(payload?.received_at??Math.floor(Date.now()/1000));
  const now=Math.floor(Date.now()/1000);
  if(!Number.isInteger(receivedAt)||receivedAt<=0) throw new Error("invalid received_at");
  if(receivedAt>now+15) throw new Error("bridge payload timestamp is too far in the future");
  if(now-receivedAt>MAX_AGE_SECONDS) throw new Error("stale bridge payload");
  const price=Number(payload?.price);
  if(!Number.isFinite(price)||price<=0) throw new Error("invalid price");
  const runtimeStatus = validateRuntimeStatus(payload?.runtime_status);
  return {symbol,timeframe,candles:normalized,liveCandle,receivedAt,price,runtimeStatus};
}

export class Mt5MarketStore {
  constructor(ctx, env) { this.state=ctx; this.env=env; }
  async fetch(request) {
    const url=new URL(request.url), symbol=(url.searchParams.get("symbol")||"EUR/USD").trim().toUpperCase(), timeframe=(url.searchParams.get("timeframe")||"15m").trim();
    if(request.method==="POST") return this.ingest(request);
    if(request.method!=="GET") return json({error:"method_not_allowed"},405);
    if(url.pathname==="/status") return this.diagnostics(symbol);
    if(!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)||!Object.prototype.hasOwnProperty.call(TIMEFRAME_SECONDS,timeframe)) return json({error:"bad_request",message:"invalid symbol or timeframe",source:"mt5"},400);
    const stored=await this.state.storage.get(key(symbol,timeframe));
    if(!stored) return json({error:"mt5_feed_unavailable",message:"no MT5 data received",source:"mt5",contract:MARKET_CONTRACT_VERSION},503);
    const age=Math.max(0,Math.floor(Date.now()/1000)-Number(stored.received_at));
    if(age>MAX_AGE_SECONDS) return json({error:"mt5_feed_unavailable",message:"MT5 bridge data is stale",source:"mt5",age_seconds:age,contract:MARKET_CONTRACT_VERSION},503);
    const candles=Array.isArray(stored.candles)?stored.candles:[];
    try {
      assertCompletedChronology(candles);
      assertCompletedCandleSeparation(candles, stored.live_candle);
    } catch(error) {
      return json({error:"mt5_market_contract_rejected",message:error?.message||"stored market snapshot is invalid",source:"mt5",execution:"NONE"},503);
    }
    const fingerprint=stored.market_fingerprint||await completedFingerprint(symbol,timeframe,candles);
    return json({symbol,timeframe,candles,live_candle:stored.live_candle,price:stored.price,source:"mt5",market_fingerprint:fingerprint,data_quality:{ok:true,age_seconds:age,mode:"BROKER_FEED"},received_at:stored.received_at,execution:"NONE"});
  }
  async diagnostics(symbol) {
    const now=Math.floor(Date.now()/1000), rows=[];
    const runtimeStatus=await this.state.storage.get("runtime_status");
    const runtimeUpdatedAt=runtimeStatus?.updated_at ? Date.parse(runtimeStatus.updated_at) : NaN;
    const runtimeAge=Number.isFinite(runtimeUpdatedAt) ? Math.max(0, Math.floor(Date.now()/1000 - runtimeUpdatedAt/1000)) : null;
    for(const timeframe of Object.keys(TIMEFRAME_SECONDS)){
      const stored=await this.state.storage.get(key(symbol,timeframe));
      if(!stored){rows.push({timeframe,state:"NO_DATA",age_seconds:null,candles:0,live_candle:false,market_fingerprint:null});continue;}
      const age=Math.max(0,now-Number(stored.received_at));
      rows.push({timeframe,state:age>MAX_AGE_SECONDS?"STALE":"LIVE",age_seconds:age,candles:Array.isArray(stored.candles)?stored.candles.length:0,live_candle:Boolean(stored.live_candle),price:Number(stored.price),market_fingerprint:stored.market_fingerprint||null});
    }
    return json({source:"mt5",contract:MARKET_CONTRACT_VERSION,symbol,timeframes:rows,runtime_status:runtimeStatus||null,runtime_status_age_seconds:runtimeAge,summary:{live:rows.filter(r=>r.state==="LIVE").length,no_data:rows.filter(r=>r.state==="NO_DATA").length,stale:rows.filter(r=>r.state==="STALE").length,runtime:runtimeStatus?.runtime_state||"NO_STATUS"}});
  }
  async ingest(request) {
    try {
      const body=await request.arrayBuffer();
      if(body.byteLength>MAX_INGEST_BYTES) return json({error:"payload_too_large",message:"MT5 bridge payload exceeds 256 KiB"},413);
      const payload=validatePayload(JSON.parse(new TextDecoder().decode(body)));
      const candles=payload.candles.slice(-MAX_CANDLES), latest=payload.liveCandle||candles.at(-1);
      if(!latest) throw new Error("payload contains no candle");
      const existing=await this.state.storage.get(key(payload.symbol,payload.timeframe)), existingLatest=existing?.live_candle||existing?.candles?.at(-1);
      if(existingLatest&&latest.time<existingLatest.time) return json({error:"out_of_order",message:"older candle payload rejected"},409);
      const fingerprint=await completedFingerprint(payload.symbol,payload.timeframe,candles);
      await this.state.storage.put(key(payload.symbol,payload.timeframe),{candles,live_candle:payload.liveCandle,price:payload.price,received_at:payload.receivedAt,market_fingerprint:fingerprint});
      if (payload.runtimeStatus) await this.state.storage.put("runtime_status", payload.runtimeStatus);
      return json({ok:true,symbol:payload.symbol,timeframe:payload.timeframe,source:"mt5",contract:MARKET_CONTRACT_VERSION,market_fingerprint:fingerprint,runtime_status:payload.runtimeStatus});
    } catch(error) { return json({error:"bad_request",message:error?.message||"invalid MT5 payload"},400); }
  }
}
export { TIMEFRAME_SECONDS, MARKET_CONTRACT_VERSION, canonicalCompletedPayload, completedFingerprint, validateCandle, validateRuntimeStatus, assertCompletedChronology, assertCompletedCandleSeparation };
