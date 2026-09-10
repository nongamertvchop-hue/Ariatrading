const TIMEFRAME_SECONDS = Object.freeze({"1m":60,"5m":300,"15m":900,"30m":1800,"1h":3600,"4h":14400,"1D":86400});
const MAX_CANDLES = 500;
const MAX_AGE_SECONDS = 90;
const MAX_INGEST_BYTES = 256 * 1024;
const MARKET_CONTRACT_VERSION = "mt5-market-v4";

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type":"application/json; charset=utf-8", "cache-control":"no-store", "x-webaria-market-contract": MARKET_CONTRACT_VERSION, ...extraHeaders } });
}
function key(symbol, timeframe) { return `${symbol}:${timeframe}`; }
function validateCandle(raw) {
  const time=Number(raw?.time), open=Number(raw?.open), high=Number(raw?.high), low=Number(raw?.low), close=Number(raw?.close);
  if (!Number.isInteger(time)||time<=0) throw new Error("invalid candle time");
  if (![open,high,low,close].every(Number.isFinite)) throw new Error("invalid candle OHLC");
  if (high<Math.max(open,close)||low>Math.min(open,close)||high<low) throw new Error("invalid candle OHLC relationship");
  return {time,open,high,low,close};
}
function validatePayload(payload) {
  const symbol=String(payload?.symbol||"").trim().toUpperCase(), timeframe=String(payload?.timeframe||"").trim();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) throw new Error("invalid symbol");
  if (!Object.prototype.hasOwnProperty.call(TIMEFRAME_SECONDS,timeframe)) throw new Error("invalid timeframe");
  const candles=Array.isArray(payload?.candles)?payload.candles:[];
  if(candles.length>MAX_CANDLES) throw new Error("too many candles");
  const normalized=candles.map(c=>validateCandle(c));
  const liveCandle=payload?.live_candle?validateCandle(payload.live_candle):null;
  const receivedAt=Number(payload?.received_at??Math.floor(Date.now()/1000));
  if(!Number.isInteger(receivedAt)||receivedAt<=0) throw new Error("invalid received_at");
  if(Math.floor(Date.now()/1000)-receivedAt>MAX_AGE_SECONDS) throw new Error("stale bridge payload");
  const price=Number(payload?.price);
  if(!Number.isFinite(price)) throw new Error("invalid price");
  return {symbol,timeframe,candles:normalized,liveCandle,receivedAt,price};
}
function assertCompletedCandleSeparation(candles, liveCandle) {
  if (!liveCandle) return;
  if (candles.some(c => c.time === liveCandle.time)) throw new Error("live candle must not be duplicated in completed candles");
}

export class Mt5MarketStore {
  constructor(ctx, env) { this.state=ctx; this.env=env; }
  async fetch(request) {
    const url=new URL(request.url), symbol=(url.searchParams.get("symbol")||"EUR/USD").trim().toUpperCase(), timeframe=(url.searchParams.get("timeframe")||"15m").trim();
    if(request.method==="POST") return this.ingest(request);
    if(request.method!=="GET") return json({error:"method_not_allowed"},405);
    if(!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)||!Object.prototype.hasOwnProperty.call(TIMEFRAME_SECONDS,timeframe)) return json({error:"bad_request",message:"invalid symbol or timeframe",source:"mt5"},400);
    const stored=await this.state.storage.get(key(symbol,timeframe));
    if(!stored) return json({error:"mt5_feed_unavailable",message:"no MT5 data received",source:"mt5"},503);
    const age=Math.max(0,Math.floor(Date.now()/1000)-stored.received_at);
    if(age>MAX_AGE_SECONDS) return json({error:"mt5_feed_unavailable",message:"MT5 bridge data is stale",source:"mt5",age_seconds:age},503);
    return json({symbol,timeframe,candles:stored.candles,live_candle:stored.live_candle,price:stored.price,source:"mt5",data_quality:{ok:true,age_seconds:age,mode:"BROKER_FEED"},received_at:stored.received_at,execution:"NONE"});
  }
  async ingest(request) {
    try {
      const body=await request.arrayBuffer();
      if(body.byteLength>MAX_INGEST_BYTES) return json({error:"payload_too_large",message:"MT5 bridge payload exceeds 256 KiB"},413);
      const payload=validatePayload(JSON.parse(new TextDecoder().decode(body)));
      assertCompletedCandleSeparation(payload.candles,payload.liveCandle);
      const candles=payload.candles.sort((a,b)=>a.time-b.time), latest=payload.liveCandle||candles.at(-1);
      if(!latest) throw new Error("payload contains no candle");
      const existing=await this.state.storage.get(key(payload.symbol,payload.timeframe)), existingLatest=existing?.live_candle||existing?.candles?.at(-1);
      if(existingLatest&&latest.time<existingLatest.time) return json({error:"out_of_order",message:"older candle payload rejected"},409);
      await this.state.storage.put(key(payload.symbol,payload.timeframe),{candles:candles.slice(-MAX_CANDLES),live_candle:payload.liveCandle,price:payload.price,received_at:payload.receivedAt});
      return json({ok:true,symbol:payload.symbol,timeframe:payload.timeframe,source:"mt5"});
    } catch(error) { return json({error:"bad_request",message:error?.message||"invalid MT5 payload"},400); }
  }
}
export { TIMEFRAME_SECONDS, MARKET_CONTRACT_VERSION };
