/* Webaria live market bridge. MT5 broker feed is the single chart and strategy source of truth. */
(function(){'use strict';
  const originalFetch=window.fetch.bind(window), POLL_MS=3000;
  async function liveMarket(symbol,timeframe){
    const url=`/api/market?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const response=await originalFetch(url,{cache:'no-store'});let payload;
    try{payload=await response.json();}catch{throw new Error(`Live market returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok||payload.source!=='mt5'){
      const contract=response.headers.get('x-webaria-market-contract')||'unknown-contract';
      const detail=payload.message||payload.error||`MT5 broker feed unavailable (HTTP ${response.status})`;
      throw new Error(`${detail} · HTTP ${response.status} · ${contract}`);
    }
    if(typeof payload.market_fingerprint!=='string'||!/^[0-9a-f]{64}$/.test(payload.market_fingerprint))throw new Error('MT5 market snapshot fingerprint is missing or invalid');
    return payload;
  }
  async function evaluateStrategy(symbol,timeframe){
    const url=`/api/signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const response=await originalFetch(url,{cache:'no-store'});let payload;
    try{payload=await response.json();}catch{throw new Error(`Strategy returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok||payload.source!=='mt5')throw new Error(payload.message||payload.error||`Strategy unavailable (HTTP ${response.status})`);
    if(typeof payload.market_fingerprint!=='string'||!/^[0-9a-f]{64}$/.test(payload.market_fingerprint))throw new Error('strategy market snapshot fingerprint is missing or invalid');
    return payload;
  }
  function normalizeTime(value){const n=Number(value);if(Number.isFinite(n)&&n>0&&Math.abs(n)<1e11)return n*1000;const parsed=Date.parse(value);return Number.isFinite(parsed)?parsed:NaN;}
  function normalizeCandle(raw){if(!raw)return null;const candle={time:normalizeTime(raw.time??raw.datetime),open:Number(raw.open),high:Number(raw.high),low:Number(raw.low),close:Number(raw.close)};if(!Number.isFinite(candle.time)||![candle.open,candle.high,candle.low,candle.close].every(Number.isFinite))return null;if(candle.high<Math.max(candle.open,candle.close)||candle.low>Math.min(candle.open,candle.close)||candle.high<candle.low)return null;return candle;}
  function normalizeCandles(candles){const rows=(Array.isArray(candles)?candles:[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.time-b.time),out=[];for(const candle of rows){if(out.length&&out[out.length-1].time===candle.time)throw new Error('MT5 completed candle history contains duplicate timestamps');out.push(candle);}return out;}
  function status(text,live){const node=document.getElementById('status');if(!node)return;node.textContent=text;node.dataset.marketState=live?'LIVE':'UNAVAILABLE';}
  function renderLiveQuote(payload,liveCandle){const price=Number(payload.price),quote=document.getElementById('quote');if(quote&&Number.isFinite(price))quote.textContent=price.toFixed(Math.abs(price)>=20?3:5);const legend=document.getElementById('legend'),symbol=payload.symbol||window.S?.symbol||'EUR/USD',tf=payload.timeframe||window.S?.tf||'15m';if(legend&&liveCandle){const f=v=>Number.isFinite(Number(v))?Number(v).toFixed(Math.abs(Number(v))>=20?3:5):'—';legend.innerHTML=`<div class="title">${symbol} · ${tf} · MT5 LIVE</div><div class="ohlc">O ${f(liveCandle.open)} H ${f(liveCandle.high)} L ${f(liveCandle.low)} C ${f(price)}</div>`;}}
  async function poll(){if(!window.S?.symbol||!window.S?.tf)return;try{const payload=await liveMarket(window.S.symbol,window.S.tf),completed=normalizeCandles(payload.candles),liveCandle=normalizeCandle(payload.live_candle);if(!completed.length)throw new Error('MT5 returned incomplete candle history');const last=completed.at(-1);if(!liveCandle||liveCandle.time<=last.time)throw new Error('MT5 forming candle is not newer than completed history');const displayCandles=completed.slice();displayCandles.push(liveCandle);window.S.candles=displayCandles;window.S.price=Number(payload.price);renderLiveQuote(payload,liveCandle);const strategy=await evaluateStrategy(window.S.symbol,window.S.tf);if(strategy.market_fingerprint!==payload.market_fingerprint)throw new Error('MT5 chart and strategy snapshots differ; refusing mixed-state render');const preservePrevious=strategy.no_update===true&&window.S.signal?.market_fingerprint===strategy.market_fingerprint;window.S.signal=preservePrevious?{...window.S.signal,price:window.S.price,live_candle:payload.live_candle,market_fingerprint:strategy.market_fingerprint,source:'mt5',data_quality:strategy.data_quality}:{...strategy,live_candle:payload.live_candle,price:window.S.price,source:'mt5'};status(`MT5 LIVE · STRATEGY LIVE · ${new Date().toLocaleTimeString()}`,true);if(typeof window.renderSignal==='function')window.renderSignal(window.S.signal);if(typeof window.WebariaObservedSignalJournalUI?.observe==='function'&&!preservePrevious)window.WebariaObservedSignalJournalUI.observe(window.S.signal,window.S.symbol,window.S.tf);if(typeof window.draw==='function')window.draw();}catch(error){status(`MT5 DATA UNAVAILABLE · ${error?.message||'broker feed error'}`,false);}}
  window.WebariaLiveMarket=Object.freeze({poll});setTimeout(poll,0);setInterval(poll,POLL_MS);
})();
