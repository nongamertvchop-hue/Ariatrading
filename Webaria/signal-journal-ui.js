/* Browser-local observed-signal journal for the Webaria terminal.
 * This records what the API reported at polling time; it does not invent or
 * backfill strategy signals, so it remains safe for later replay analysis.
 */
(function(root){
  'use strict';
  const KEY='webaria-observed-signals-v1';
  const MAX=100;
  const scope=(symbol,tf)=>`${symbol}|${tf}`;
  function read(symbol,tf){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');return Array.isArray(all[scope(symbol,tf)])?all[scope(symbol,tf)]:[]}catch{return []}}
  function write(symbol,tf,entries){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');all[scope(symbol,tf)]=entries.slice(-MAX);localStorage.setItem(KEY,JSON.stringify(all));}catch{}}
  function record(entry){
    if(!entry||!entry.symbol||!entry.tf||!entry.bar_time)return;
    const list=read(entry.symbol,entry.tf);
    const key=`${entry.bar_time}|${entry.signal||'WAIT'}`;
    const idx=list.findIndex(x=>`${x.bar_time}|${x.signal||'WAIT'}`===key);
    if(idx>=0){list[idx]=entry;write(entry.symbol,entry.tf,list);return}
    list.push(entry);write(entry.symbol,entry.tf,list);
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
      const time=x.bar_time?new Date(Number(x.bar_time)).toLocaleString():new Date(x.observed_at||Date.now()).toLocaleTimeString();
      const score=x.score==null?'—':x.score;
      const source=x.source||'unknown';
      return `<div class="journal-row"><div><span class="journal-sig ${cls}">${sig}</span><div class="journal-meta">${time} · ${source}</div></div><div class="journal-meta">S:${score}</div></div>`;
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
    render(symbol,tf);
  }
  function bind(){
    const clearButton=document.getElementById('clearJournal');
    if(clearButton)clearButton.onclick=()=>{const symbol=document.getElementById('symbol')?.value||'EUR/USD',tf=document.getElementById('tf')?.value||'15m';clear(symbol,tf);render(symbol,tf)};
    const refresh=()=>render(document.getElementById('symbol')?.value||'EUR/USD',document.getElementById('tf')?.value||'15m');
    refresh();
  }
  root.WebariaObservedSignalJournalUI=Object.freeze({observe,render,bind});
  window.addEventListener('DOMContentLoaded',bind);
})(typeof window!=='undefined'?window:globalThis);
