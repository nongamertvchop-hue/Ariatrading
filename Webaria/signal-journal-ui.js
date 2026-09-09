/* Browser-local observed-signal journal for the Webaria terminal.
 * This records what the API reported at polling time; it does not invent or
 * backfill strategy signals, so it remains safe for later replay analysis.
 */
(function(root){
  'use strict';
  const KEY='webaria-observed-signals-v1';
  const MAX=100;
  function scope(symbol,tf){return `${symbol}|${tf}`;}
  function read(symbol,tf){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');return Array.isArray(all[scope(symbol,tf)])?all[scope(symbol,tf)]:[]}catch{return []}}
  function write(symbol,tf,entries){try{const all=JSON.parse(localStorage.getItem(KEY)||'{}');all[scope(symbol,tf)]=entries.slice(-MAX);localStorage.setItem(KEY,JSON.stringify(all));}catch{}}
  function record(entry){
    if(!entry||!entry.symbol||!entry.tf||!entry.bar_time)return;
    const list=read(entry.symbol,entry.tf);
    const key=`${entry.bar_time}|${entry.signal||'WAIT'}|${entry.observed_at||''}`;
    if(list.some(x=>`${x.bar_time}|${x.signal||'WAIT'}|${x.observed_at||''}`===key))return;
    list.push(entry);write(entry.symbol,entry.tf,list);
  }
  function clear(symbol,tf){write(symbol,tf,[]);}
  root.WebariaObservedSignalJournal=Object.freeze({record,read,clear});
})(typeof window!=='undefined'?window:globalThis);
