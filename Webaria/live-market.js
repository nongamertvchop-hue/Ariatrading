/* Webaria live market bridge. Prefer the MT5 runtime, but never blank the terminal when the broker bridge is unavailable. */
(function(){'use strict';
  const originalFetch=window.fetch.bind(window), POLL_MS=3000;
  let pollGeneration=0;

  function normalizeTime(value){const n=Number(value);if(Number.isFinite(n)&&n>0&&Math.abs(n)<1e11)return n*1000;const parsed=Date.parse(value);return Number.isFinite(parsed)?parsed:NaN;}
  function normalizeCandle(raw){if(!raw)return null;const candle={time:normalizeTime(raw.time??raw.datetime),open:Number(raw.open),high:Number(raw.high),low:Number(raw.low),close:Number(raw.close)};if(!Number.isFinite(candle.time)||![candle.open,candle.high,candle.low,candle.close].every(Number.isFinite))return null;if(candle.high<Math.max(candle.open,candle.close)||candle.low>Math.min(candle.open,candle.close)||candle.high<candle.low)return null;return candle;}
  function normalizeCandles(candles){const rows=(Array.isArray(candles)?candles:[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.time-b.time),out=[];for(const candle of rows){if(out.length&&out[out.length-1].time===candle.time)out[out.length-1]=candle;else out.push(candle);}return out;}
  function status(text,live){const node=document.getElementById('status');if(!node)return;node.textContent=text;node.dataset.marketState=live?'LIVE':'SIMULATION';}
  function decorateSignal(payload,source){return {...payload,source,execution:'NONE'};}

  async function mt5Market(symbol,timeframe){
    const response=await originalFetch(`/api/market?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,{cache:'no-store'});
    let payload;try{payload=await response.json();}catch{throw new Error(`market returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok||payload.source!=='mt5')throw new Error(payload.message||payload.error||`MT5 market unavailable (HTTP ${response.status})`);
    return payload;
  }

  async function strategyForCandles(symbol,timeframe,candles,source){
    const response=await originalFetch('/api/strategy',{method:'POST',cache:'no-store',headers:{'content-type':'application/json'},body:JSON.stringify({symbol,timeframe,candles,source})});
    let payload;try{payload=await response.json();}catch{throw new Error(`strategy returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok)throw new Error(payload.message||payload.error||`strategy unavailable (HTTP ${response.status})`);
    return payload;
  }

  async function simulationMarket(symbol,timeframe){
    const response=await originalFetch(`/api/signal?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`,{cache:'no-store'});
    let payload;try{payload=await response.json();}catch{throw new Error(`simulation signal returned invalid JSON (HTTP ${response.status})`);}
    if(!response.ok)throw new Error(payload.message||payload.error||`signal endpoint unavailable (HTTP ${response.status})`);
    return decorateSignal(payload,payload.source||'simulation');
  }

  function renderPayload(payload,liveCandleLabel){
    const state=window.S;if(!state)return;
    const completed=normalizeCandles(payload.candles);
    const rawLive=payload.live_candle||payload.candle||completed.at(-1);
    const liveCandle=normalizeCandle(rawLive);
    if(!completed.length&&!liveCandle)throw new Error('no valid candles returned');
    const displayCandles=completed.slice();
    if(liveCandle){const last=displayCandles.at(-1);if(!last||liveCandle.time>last.time)displayCandles.push(liveCandle);else if(liveCandle.time===last.time)displayCandles[displayCandles.length-1]=liveCandle;}
    state.candles=displayCandles;
    const price=Number(payload.price??liveCandle?.close??completed.at(-1)?.close);if(Number.isFinite(price))state.price=price;
    state.signal=payload;
    const quote=document.getElementById('quote');if(quote&&Number.isFinite(state.price))quote.textContent=state.price.toFixed(Math.abs(state.price)>=20?3:5);
    const legend=document.getElementById('legend');if(legend&&liveCandle){const f=v=>Number.isFinite(Number(v))?Number(v).toFixed(Math.abs(Number(v))>=20?3:5):'—';legend.innerHTML=`<div class="title">${state.symbol} · ${state.tf} · ${liveCandleLabel}</div><div class="ohlc">O ${f(liveCandle.open)} H ${f(liveCandle.high)} L ${f(liveCandle.low)} C ${f(liveCandle.close)}</div>`;}
    if(typeof window.renderSignal==='function')window.renderSignal(payload);
    if(typeof window.WebariaObservedSignalJournalUI?.observe==='function')window.WebariaObservedSignalJournalUI.observe(payload,state.symbol,state.tf);
    if(typeof window.draw==='function')window.draw();
    status(`${liveCandleLabel} · ${new Date().toLocaleTimeString()}`,liveCandleLabel.includes('MT5'));
  }

  async function poll(){
    const state=window.S;if(!state?.symbol||!state?.tf)return;
    const generation=++pollGeneration,symbol=state.symbol,timeframe=state.tf;
    try{
      try{
        const payload=await mt5Market(symbol,timeframe);
        if(generation!==pollGeneration||window.S?.symbol!==symbol||window.S?.tf!==timeframe)return;
        const completed=normalizeCandles(payload.candles);
        if(!completed.length)throw new Error('MT5 returned no completed candles');
        const strategy=await strategyForCandles(symbol,timeframe,completed.slice(-100),'mt5');
        const merged={...payload,...strategy,candles:completed,source:'mt5',execution:'NONE'};
        if(generation!==pollGeneration||window.S?.symbol!==symbol||window.S?.tf!==timeframe)return;
        renderPayload(merged,'MT5 LIVE');
        return;
      }catch(mt5Error){
        const payload=await simulationMarket(symbol,timeframe);
        if(generation!==pollGeneration||window.S?.symbol!==symbol||window.S?.tf!==timeframe)return;
        renderPayload(payload,`PAPER/SIMULATION · ${payload.source||'fallback'}`);
        const note=document.getElementById('reason');if(note)note.textContent=`MT5 bridge unavailable: ${mt5Error.message}. Showing simulation data so the terminal remains usable.`;
      }
    }catch(error){
      if(generation===pollGeneration&&window.S?.symbol===symbol&&window.S?.tf===timeframe)status(`DATA ERROR · ${error?.message||'market error'}`,false);
    }
  }

  window.WebariaLiveMarket=Object.freeze({poll});
  setTimeout(poll,0);
  setInterval(poll,POLL_MS);
})();
