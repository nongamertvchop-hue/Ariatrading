/* Browser-local observed-signal journal for the Webaria terminal.
 * Signals are recorded exactly as observed from /api/signal.
 * Outcomes are computed only from candles strictly AFTER the signal bar,
 * which keeps replay/outcome statistics free of future-data leakage.
 */
(function(root){
  'use strict';
  const KEY='webaria-observed-signals-v1';
  const MAX=100;
  const HORIZONS=[1,3,5];
  const scope=(symbol,tf)=>`${symbol}|${tf}`;
  const numTime=v=>{const n=Number(v);return Number.isFinite(n)?n:Date.parse(v)};
  const candlesAsc=c=>Array.isArray(c)?c.slice().filter(x=>x&&Number.isFinite(+x.close)).sort((a,b)=>numTime(a.time??a.datetime)-numTime(b.time??b.datetime)):[];
  function read(symbol,tf){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');return Array.isArray(all[scope(symbol,tf)])?all[scope(symbol,tf)]:[]}catch{return []}}
  function write(symbol,tf,entries){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');all[scope(symbol,tf)]=entries.slice(-MAX);localStorage.setItem(KEY,JSON.stringify(all));}catch{}}
  function record(entry){
    if(!entry||!entry.symbol||!entry.tf||entry.bar_time==null)return;
    const list=read(entry.symbol,entry.tf);
    const key=`${entry.bar_time}|${entry.signal||'WAIT'}`;
    const idx=list.findIndex(x=>`${x.bar_time}|${x.signal||'WAIT'}`===key);
    if(idx>=0)list[idx]={...list[idx],...entry};else list.push(entry);
    write(entry.symbol,entry.tf,list);
  }
  function clear(symbol,tf){write(symbol,tf,[])}
  function updateOutcomes(symbol,tf,candles){
    const data=candlesAsc(candles);if(!data.length)return;
    const list=read(symbol,tf);let changed=false;
    for(const entry of list){
      if(!['LONG','SHORT'].includes(String(entry.signal||'')))continue;
      const t=numTime(entry.bar_time);if(!Number.isFinite(t))continue;
      const i=data.findIndex(c=>numTime(c.time??c.datetime)===t);if(i<0)continue;
      const base=+data[i].close;if(!Number.isFinite(base)||base===0)continue;
      const outcome=entry.outcome&&typeof entry.outcome==='object'?entry.outcome:{};
      let entryChanged=false;
      for(const horizon of HORIZONS){
        const end=i+horizon;if(end>=data.length)continue;
        const window=data.slice(i+1,end+1);
        const direction=entry.signal==='LONG'?1:-1;
        const closePct=((+data[end].close-base)/base)*100*direction;
        const mfe=Math.max(...window.map(c=>(((entry.signal==='LONG'?+c.high:+c.low)-base)/base)*100*direction));
        const mae=Math.min(...window.map(c=>(((entry.signal==='LONG'?+c.low:+c.high)-base)/base)*100*direction));
        const next={close_pct:Number(closePct.toFixed(5)),mfe_pct:Number(mfe.toFixed(5)),mae_pct:Number(mae.toFixed(5)),bars:horizon,completed:true};
        if(JSON.stringify(outcome[horizon])!==JSON.stringify(next)){outcome[horizon]=next;entryChanged=true;}
      }
      if(entryChanged){entry.outcome=outcome;changed=true;}
    }
    if(changed)write(symbol,tf,list);
  }
  function statText(x){
    const o=x.outcome||{};
    return HORIZONS.map(h=>o[h]?`${h}:${o[h].close_pct>=0?'+':''}${o[h].close_pct.toFixed(2)}%`:`${h}:—`).join(' ');
  }
  function render(symbol,tf){
    const box=document.getElementById('journal');if(!box)return;
    const list=read(symbol,tf).slice().reverse().slice(0,12);
    if(!list.length){box.innerHTML='<div class="journal-empty">No observations yet.</div>';return;}
    box.innerHTML=list.map(x=>{
      const sig=String(x.signal||'WAIT'),cls=sig==='LONG'?'up':sig==='SHORT'?'down':'';
      const raw=numTime(x.bar_time);const time=Number.isFinite(raw)?new Date(raw).toLocaleString():String(x.bar_time);
      const score=x.score==null?'—':x.score;const outcome=statText(x);
      return `<div class="journal-row"><div><span class="journal-sig ${cls}">${sig}</span><div class="journal-meta">${time} · ${x.source||'unknown'}</div><div class="journal-outcome">${sig==='WAIT'?'No directional outcome':outcome}</div></div><div class="journal-meta">S:${score}</div></div>`;
    }).join('');
  }
  function observe(j,symbol,tf){
    const candles=Array.isArray(j?.candles)?j.candles:[];const last=candles[candles.length-1];const barTime=last?.time??last?.datetime;if(barTime==null)return;
    record({event_id:`${symbol}|${tf}|${barTime}`,symbol,tf,bar_time:barTime,signal:j?.signal||j?.direction||'WAIT',state:j?.state||null,structure:j?.structure_bias||null,breakout:j?.breakout_state||null,score:j?.score??null,source:j?.source||'unknown',observed_at:j?.generated_at||new Date().toISOString()});
    updateOutcomes(symbol,tf,candles);
    const selectedSymbol=document.getElementById('symbol')?.value,selectedTf=document.getElementById('tf')?.value;
    if(symbol===selectedSymbol&&tf===selectedTf)render(symbol,tf);
  }
  function inspectRequest(input){try{const url=new URL(typeof input==='string'?input:input?.url||'',window.location.href);if(url.pathname!=='/api/signal')return null;return {symbol:url.searchParams.get('symbol')||'EUR/USD',tf:url.searchParams.get('timeframe')||'15m'};}catch{return null}}
  function bind(){
    const clearButton=document.getElementById('clearJournal');
    if(clearButton)clearButton.onclick=()=>{const symbol=document.getElementById('symbol')?.value||'EUR/USD',tf=document.getElementById('tf')?.value||'15m';clear(symbol,tf);render(symbol,tf)};
    render(document.getElementById('symbol')?.value||'EUR/USD',document.getElementById('tf')?.value||'15m');
  }
  const originalFetch=root.fetch.bind(root);
  root.fetch=async function(input,init){const meta=inspectRequest(input);const response=await originalFetch(input,init);if(meta)response.clone().json().then(payload=>observe(payload,meta.symbol,meta.tf)).catch(()=>{});return response;};
  root.WebariaObservedSignalJournalUI=Object.freeze({observe,render,bind,read,updateOutcomes});
  window.addEventListener('DOMContentLoaded',bind);
})(typeof window!=='undefined'?window:globalThis);
