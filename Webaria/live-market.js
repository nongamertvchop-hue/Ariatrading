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
    return payload;
  }
  async function evaluateStrategy(symbol,timeframe){
    const url=`/api/signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`;
    const response=await originalFetch(url,{cache:'no-store'});let payload;
    try{payload=await response.json();}catch{throw new Error(`Strategy returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok||payload.source!=='mt5')throw new Error(payload.message||payload.error||`Strategy unavailable (HTTP ${response.status})`);
    return payload;
  }
  function normalizeTime(value){const n=Number(value);if(Number.isFinite(n)&&n>0&&Math.abs(n)<1e11)return n*1000;const parsed=Date.parse(value);return Number.isFinite(parsed)?parsed:NaN;}
  function normalizeCandle(raw){if(!raw)return null;const candle={time:normalizeTime(raw.time??raw.datetime),open:Number(raw.open),high:Number(raw.high),low:Number(raw.low),close:Number(raw.close)};if(!Number.isFinite(candle.time)||![candle.open,candle.high,candle.low,candle.close].every(Number.isFinite))return null;if(candle.high<Math.max(candle.open,candle.close)||candle.low>Math.min(candle.open,candle.close)||candle.high<candle.low)return null;return candle;}
  function normalizeCandles(candles){const rows=(Array.isArray(candles)?candles:[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.time-b.time),out=[];for(const candle of rows){if(out.length&&out[out.length-1].time===candle.time)out[out.length-1]=candle;else out.push(candle);}return out;}
  function status(text,live){const node=document.getElementById('status');if(!node)return;node.textContent=text;node.dataset.marketState=live?'LIVE':'UNAVAILABLE';}
  function renderLiveQuote(payload,liveCandle){const price=Number(payload.price),quote=document.getElementById('quote');if(quote&&Number.isFinite(price))quote.textContent=price.toFixed(Math.abs(price)>=20?3:5);const legend=document.getElementById('legend'),symbol=payload.symbol||window.S?.symbol||'EUR/USD',tf=payload.timeframe||window.S?.tf||'15m';if(legend&&liveCandle){const f=v=>Number.isFinite(Number(v))?Number(v).toFixed(Math.abs(Number(v))>=20?3:5):'—';legend.innerHTML=`<div class="title">${symbol} · ${tf} · MT5 LIVE</div><div class="ohlc">O ${f(liveCandle.open)} H ${f(liveCandle.high)} L ${f(liveCandle.low)} C ${f(price)}</div>`;}}
  async function poll(){const state=window.S;if(!state?.symbol||!state?.tf)return;try{const payload=await liveMarket(state.symbol,state.tf),completed=normalizeCandles(payload.candles),liveCandle=normalizeCandle(payload.live_candle);if(!completed.length)throw new Error('MT5 returned incomplete candle history');const displayCandles=completed.slice(),last=displayCandles.at(-1);if(liveCandle&&(!last||liveCandle.time>last.time))displayCandles.push(liveCandle);else if(liveCandle&&last&&liveCandle.time===last.time)displayCandles[displayCandles.length-1]=liveCandle;state.candles=displayCandles;state.price=Number(payload.price);renderLiveQuote(payload,liveCandle);const strategy=await evaluateStrategy(state.symbol,state.tf);state.signal={...strategy,live_candle:payload.live_candle,price:state.price,source:'mt5'};status(`MT5 LIVE · STRATEGY LIVE · ${new Date().toLocaleTimeString()}`,true);if(typeof window.renderSignal==='function')window.renderSignal(state.signal);if(typeof window.WebariaObservedSignalJournalUI?.observe==='function')window.WebariaObservedSignalJournalUI.observe(state.signal,state.symbol,state.tf);if(typeof window.draw==='function')window.draw();}catch(error){status(`MT5 DATA UNAVAILABLE · ${error?.message||'broker feed error'}`,false);}}
  window.WebariaLiveMarket=Object.freeze({poll});setTimeout(poll,0);setInterval(poll,POLL_MS);
})();
