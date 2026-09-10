import app from "./index.js";
import { onRequestGet as marketRequest } from "../Webaria/functions/api/market.js";
import { Mt5MarketStore } from "./mt5_market.js";
import { handleSignalParityV2, evaluateRealtimeSignalParity } from "./signal_parity_v2.js";
import { buildSignalEventId } from "./signal_event.js";
import { fallbackCandles, fallbackPrice, FALLBACK_SOURCE, TIMEFRAME_SECONDS } from "./fallback_market.js";
import { guardPublicRequest, applySecurityHeaders, statusResponse, BODYGUARD_VERSION } from "../bodyguard/worker/bodyguard.js";
import { sanitizeForBoundary } from "../bodyguard/worker/redaction.js";

const FRESH_TTL_MS = Object.freeze({"/api/price":10000,"/api/signal":30000,"/api/live-candle":10000,"/api/market":2000});
const STALE_TTL_MS = Object.freeze({"/api/price":5*60000,"/api/signal":5*60000,"/api/live-candle":2*60000,"/api/market":30000});
const MAX_RESPONSE_CACHE_ENTRIES=256;
const responseCache=new Map();
function cacheKey(request){const url=new URL(request.url);if(!url.pathname.startsWith("/api/"))return request.method+":"+url.pathname;const symbol=(url.searchParams.get("symbol")||"EUR/USD").trim().toUpperCase(),timeframe=(url.searchParams.get("timeframe")||"15m").trim();return `${request.method}:${url.pathname}:symbol=${symbol}:timeframe=${timeframe}`;}
function evictOldestCacheEntry(){if(responseCache.size<MAX_RESPONSE_CACHE_ENTRIES)return;const oldest=responseCache.keys().next().value;if(oldest!==undefined)responseCache.delete(oldest);}
function cloneHeaders(response,extra={}){const headers=new Headers(response.headers);for(const[name,value]of Object.entries(extra))headers.set(name,value);return headers;}
function cachedResponse(record,statusOverride,cacheStatus){return applySecurityHeaders(new Response(record.body,{status:statusOverride??record.status,headers:cloneHeaders(record.headers,{"x-webaria-market-cache":cacheStatus,"cache-control":"no-store"})}));}
async function readResponse(response){return{body:await response.clone().arrayBuffer(),headers:response.headers,status:response.status,savedAt:Date.now()};}
function json(data,status=200,headers={}){return applySecurityHeaders(new Response(JSON.stringify(sanitizeForBoundary(data)),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store",...headers}}));}
function requestParams(request){const url=new URL(request.url),symbol=(url.searchParams.get("symbol")||"EUR/USD").trim().toUpperCase(),timeframe=(url.searchParams.get("timeframe")||"15m").trim();if(!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol))throw new Error("symbol must look like EUR/USD");if(!TIMEFRAME_SECONDS[timeframe])throw new Error(`unsupported timeframe: ${timeframe}`);return{symbol,timeframe};}
function fallbackSignalResponse(request){const{symbol,timeframe}=requestParams(request),candles=fallbackCandles(symbol,timeframe,100),result=evaluateRealtimeSignalParity(candles,timeframe),response={symbol,timeframe,...result,source:FALLBACK_SOURCE,data_quality:{ok:true,reason:"synthetic fallback: market-data secret is not configured",latest_time:result.bar_time,age_seconds:0,mode:"SIMULATION"},generated_at:new Date().toISOString(),execution:"NONE"};return buildSignalEventId(response).then(event_id=>json({...response,event_id},200,{"x-webaria-data-source":FALLBACK_SOURCE}));}
function fallbackPriceResponse(request){const{symbol,timeframe}=requestParams(request),price=fallbackPrice(symbol,timeframe);return json({symbol,price,source:FALLBACK_SOURCE,generated_at:new Date().toISOString(),execution:"NONE"},200,{"x-webaria-data-source":FALLBACK_SOURCE});}
function fallbackCandleResponse(request){const{symbol,timeframe}=requestParams(request),candle=fallbackCandles(symbol,timeframe,1)[0];return json({symbol,timeframe,candle,confirmed:true,source:FALLBACK_SOURCE,generated_at:new Date().toISOString(),execution:"NONE"},200,{"x-webaria-data-source":FALLBACK_SOURCE});}
async function resolveApi(request,env,ctx,pathname){
  if(pathname==="/api/bodyguard/status")return statusResponse();
  if(pathname==="/api/mt5/ingest"){
    if(request.method!=="POST")return json({error:"method_not_allowed"},405);
    const token=request.headers.get("authorization")?.replace(/^Bearer\s+/i,"");
    if(!env.MT5_BRIDGE_TOKEN||token!==env.MT5_BRIDGE_TOKEN)return json({error:"unauthorized"},401);
    const id=env.MT5_MARKET.idFromName("market");
    return env.MT5_MARKET.get(id).fetch(new Request("https://mt5.internal/ingest",{method:"POST",headers:request.headers,body:request.body}));
  }
  if(pathname==="/api/mt5/market"){
    const id=env.MT5_MARKET.idFromName("market");
    return env.MT5_MARKET.get(id).fetch(request);
  }
  if(pathname==="/api/market"){
    const id=env.MT5_MARKET.idFromName("market");
    const mt5=await env.MT5_MARKET.get(id).fetch(request);
    if(mt5.ok)return mt5;
    if(env.TWELVE_DATA_API_KEY)return marketRequest({request,env,ctx});
    return mt5;
  }
  if(!env.TWELVE_DATA_API_KEY){if(pathname==="/api/signal")return fallbackSignalResponse(request);if(pathname==="/api/price")return fallbackPriceResponse(request);if(pathname==="/api/live-candle")return fallbackCandleResponse(request);}
  if(pathname==="/api/signal")return handleSignalParityV2(request,env);
  return app.fetch(request,env,ctx);
}
export { Mt5MarketStore };
export default {async fetch(request,env,ctx){const url=new URL(request.url);if(url.pathname.startsWith("/api/")){const blocked=guardPublicRequest(request);if(blocked)return blocked;}if(url.pathname==="/api/bodyguard/status")return statusResponse();const ttl=FRESH_TTL_MS[url.pathname],staleTtl=STALE_TTL_MS[url.pathname];if(!ttl||request.method!=="GET"){const response=await resolveApi(request,env,ctx,url.pathname);return applySecurityHeaders(response);}const key=cacheKey(request),now=Date.now(),cached=responseCache.get(key);if(cached&&now-cached.savedAt<=ttl)return cachedResponse(cached,cached.status,"HIT");try{const response=await resolveApi(request,env,ctx,url.pathname);if(response.ok){const record=await readResponse(response);evictOldestCacheEntry();responseCache.set(key,record);return cachedResponse(record,record.status,"MISS");}if(cached&&now-cached.savedAt<=staleTtl)return cachedResponse(cached,200,"STALE");return applySecurityHeaders(response);}catch(_){if(cached&&now-cached.savedAt<=staleTtl)return cachedResponse(cached,200,"STALE");return json({error:"upstream_or_internal_error",message:"request could not be completed",guard:"Bodyguard(Aria)",version:BODYGUARD_VERSION},502);}}};
