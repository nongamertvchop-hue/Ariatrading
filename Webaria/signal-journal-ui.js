/* Browser-local observed-signal journal for the Webaria terminal.
 * This records what the API actually returned to the browser at polling time.
 * It deliberately does not calculate or backfill trading signals.
 */
(function(root){
  'use strict';
  const KEY='webaria-observed-signals-v1';
  const MAX=100;
  const scope=(symbol,tf)=>`${symbol}|${tf}`;
  function read(symbol,tf){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');return Array.isArray(all[scope(symbol,tf)])?all[scope(symbol,tf)]:[]}catch{return []}}
  function write(symbol,tf,entries){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');all[scope(symbol,tf)]=entries.slice(-MAX);localStorage.setItem(KEY,JSON.stringify(all));}catch{}}
  function record(entry){
    if(!entry||!entry.symbol||!entry.tf||entry.bar_time==null)return;
    const list=read(entry.symbol,entry.tf);
    const key=`${entry.bar_time}|${entry.signal||'WAIT'}`;
    const idx=list.findIndex(x=>`${x.bar_time}|${x.signal||'WAIT'}`===key);
    if(idx>=0)list[idx]=entry;else list.push(entry);
    write(entry.symbol,entry.tf,list);
  }
  function clear(symbol,tf){write(symbol,tf,[])}
  function render(symbol,tf){
    const box=document.getElementById('journal');
    if(!box)return;
    const list=read(symbol,tf).slice().reverse().slice(0,12);
    if(!list.length){box.innerHTML='<div class="journal-empty">No observations yet.</div>';return}
    box.innerHTML=list.map(x=>{
      const sig=String(x.signal||'WAIT');
      const cls=sig==='LONG'?'up':sig==='SHORT'?'down':'';
      const raw=Number(x.bar_time);
      const time=Number.isFinite(raw)?new Date(raw).toLocaleString():String(x.bar_time);
      const score=x.score==null?'—':x.score;
      return `<div class="journal-row"><div><span class="journal-sig ${cls}">${sig}</span><div class="journal-meta">${time} · ${x.source||'unknown'}</div></div><div class="journal-meta">S:${score}</div></div>`;
    }).join('');
  }
  function observe(j,symbol,tf){
    const candles=Array.isArray(j?.candles)?j.candles:[];
    const last=candles[candles.length-1];
    const barTime=last?.time??last?.datetime;
    if(barTime==null)return;
    record({
      event_id:`${symbol}|${tf}|${barTime}`,
      symbol,tf,bar_time:barTime,signal:j?.signal||j?.direction||'WAIT',
      state:j?.state||null,structure:j?.structure_bias||null,breakout:j?.breakout_state||null,
      score:j?.score??null,source:j?.source||'unknown',observed_at:j?.generated_at||new Date().toISOString()
    });
    const selectedSymbol=document.getElementById('symbol')?.value;
    const selectedTf=document.getElementById('tf')?.value;
    if(symbol===selectedSymbol&&tf===selectedTf)render(symbol,tf);
  }
  function inspectRequest(input){
    try{
      const url=new URL(typeof input==='string'?input:input?.url||'',window.location.href);
      if(url.pathname!=='/api/signal')return null;
      return {symbol:url.searchParams.get('symbol')||'EUR/USD',tf:url.searchParams.get('timeframe')||'15m'};
    }catch{return null}
  }
  function bind(){
    const clearButton=document.getElementById('clearJournal');
    if(clearButton)clearButton.onclick=()=>{const symbol=document.getElementById('symbol')?.value||'EUR/USD',tf=document.getElementById('tf')?.value||'15m';clear(symbol,tf);render(symbol,tf)};
    const refresh=()=>render(document.getElementById('symbol')?.value||'EUR/USD',document.getElementById('tf')?.value||'15m');
    refresh();
  }
  const originalFetch=root.fetch.bind(root);
  root.fetch=async function(input,init){
    const meta=inspectRequest(input);
    const response=await originalFetch(input,init);
    if(meta){
      response.clone().json().then(payload=>observe(payload,meta.symbol,meta.tf)).catch(()=>{});
    }
    return response;
  };
  root.WebariaObservedSignalJournalUI=Object.freeze({observe,render,bind});
  window.addEventListener('DOMContentLoaded',bind);
})(typeof window!=='undefined'?window:globalThis);
