/* Webaria paper terminal: durable runtime contract is authoritative; localStorage is cache/migration only. */
(function () {
  'use strict';

  const STORAGE_KEY = 'webaria-paper-account-v1';
  const START_BALANCE = 10000;
  const MAX_HISTORY = 100;
  const POLL_MS = 30000;
  const HEARTBEAT_MS = 5000;
  const API = '/api/paper-state';
  const $ = id => document.getElementById(id);

  let state = loadLocalCache();
  let authoritative = false;
  let syncBusy = false;
  let monitorBusy = false;

  function finite(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function loadLocalCache() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object') throw new Error('empty');
      return { balance: finite(saved.balance, START_BALANCE), position: saved.position && typeof saved.position === 'object' ? saved.position : null, history: Array.isArray(saved.history) ? saved.history.slice(-MAX_HISTORY) : [] };
    } catch (_) { return { balance: START_BALANCE, position: null, history: [] }; }
  }

  function cacheLocal() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {} }
  function currentSymbol() { return $('symbol')?.value || 'EUR/USD'; }
  function currentTimeframe() { return $('tf')?.value || '15m'; }
  function currentPrice() { const p = Number($('quote')?.textContent?.trim().replace(/,/g, '')); return Number.isFinite(p) && p > 0 ? p : null; }
  function pnl(position, price) { if (!position || !Number.isFinite(price)) return 0; return (price - Number(position.entry)) * (position.side === 'LONG' ? 1 : -1) * Number(position.quantity); }
  function setNote(message) { const node = $('paperNote'); if (node) node.textContent = message || 'Simulation only · durable paper runtime · orders never reach a broker'; }

  function render() {
    const position = state.position, price = currentPrice(), unrealized = position && position.symbol === currentSymbol() ? pnl(position, price) : 0, balance = finite(state.balance, START_BALANCE);
    $('balance').textContent = balance.toFixed(2); $('equity').textContent = (balance + unrealized).toFixed(2); $('pos').textContent = position ? `${position.side} ${finite(position.quantity, 0)}` : 'FLAT'; $('entry').textContent = position ? formatPrice(position.entry) : '—'; $('pnl').textContent = `${unrealized >= 0 ? '+' : ''}${unrealized.toFixed(2)}`;
    $('close').disabled = !position || position.symbol !== currentSymbol() || !Number.isFinite(price); $('buy').disabled = !!position; $('sell').disabled = !!position; $('paperMetrics').innerHTML = buildMetrics(); renderHistory();
    const note = document.querySelector('.paper-contract'); if (note) note.textContent = authoritative ? 'contract aria.paper-runtime.v1 · durable state authoritative · execution NONE' : 'contract aria.paper-runtime.v1 · syncing durable state… · execution NONE';
  }

  function buildMetrics() {
    const trades = state.history.filter(t => Number.isFinite(Number(t.pnl))), wins = trades.filter(t => Number(t.pnl) > 0), losses = trades.filter(t => Number(t.pnl) < 0), grossProfit = wins.reduce((s,t)=>s+Number(t.pnl),0), grossLoss = Math.abs(losses.reduce((s,t)=>s+Number(t.pnl),0)), pf = grossLoss ? grossProfit/grossLoss : (grossProfit > 0 ? Infinity : 0);
    let balance=START_BALANCE,peak=START_BALANCE,maxDd=0; for(const trade of state.history){const result=Number(trade.pnl);if(!Number.isFinite(result))continue;balance+=result;peak=Math.max(peak,balance);maxDd=Math.max(maxDd,peak-balance);} const winRate=trades.length?(wins.length/trades.length)*100,format=n=>Number.isFinite(n)?n.toFixed(2):'—';
    return `<div class="metric"><span>Trades</span><b>${trades.length}</b></div><div class="metric"><span>Win rate</span><b>${winRate.toFixed(1)}%</b></div><div class="metric"><span>Net P/L</span><b>${format(trades.reduce((s,t)=>s+Number(t.pnl),0))}</b></div><div class="metric"><span>Profit factor</span><b>${pf===Infinity?'∞':format(pf)}</b></div><div class="metric"><span>Max drawdown</span><b>${format(maxDd)}</b></div>`;
  }

  function renderHistory() { const node=$('history')||$('paperHistory'); if(!node)return; const rows=state.history.slice().reverse().slice(0,8); node.innerHTML=rows.length?rows.map(t=>{const result=Number(t.pnl),cls=result>0?'up':result<0?'down':'';return `<div class="paper-trade"><span>${escapeHtml(t.side)} · ${escapeHtml(t.symbol)}</span><b class="${cls}">${result>=0?'+':''}${result.toFixed(2)}</b><small>${escapeHtml(t.reason||'')}</small></div>`}).join(''):'<div class="paper-history-empty">No paper trades yet.</div>'; }
  function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
  function formatPrice(value) { const n=Number(value); return Number.isFinite(n)?n.toFixed(Math.abs(n)>=20?3:5):'—'; }

  function toDurablePayload() {
    const price=currentPrice(), unrealized=state.position&&state.position.symbol===currentSymbol()?pnl(state.position,price):0, equity=finite(state.balance,START_BALANCE)+unrealized;
    return {contract:'aria.paper-runtime.v1',mode:'PAPER',lifecycle:state.position?'OPEN':'FLAT',running:true,halted:false,haltReason:'',heartbeat:new Date().toISOString(),lastBarTime:state.position?.last_checked_bar_time||null,lastProcessedBarTime:state.position?.last_checked_bar_time||null,account:{balance:finite(state.balance,START_BALANCE),equity,realizedPnl:finite(state.balance,START_BALANCE)-START_BALANCE,unrealizedPnl:unrealized,peakEquity:Math.max(START_BALANCE,equity),drawdown:Math.max(0,START_BALANCE-equity),drawdownPct:Math.max(0,(START_BALANCE-equity)/START_BALANCE),tradeCount:state.history.length,winRate:state.history.length?state.history.filter(t=>Number(t.pnl)>0).length/state.history.length:0},position:state.position,pending:null,alerts:[],history:state.history.slice(-MAX_HISTORY),events:[{at:new Date().toISOString(),type:'BROWSER_PAPER_SYNC',source:'paper-terminal'}]};
  }

  async function readDurable() {
    try { const response=await fetch(API,{cache:'no-store',headers:{accept:'application/json'}}),payload=await response.json(); if(!response.ok||payload?.contract!=='aria.paper-runtime.v1')throw new Error(payload?.message||`HTTP ${response.status}`); const account=payload.account||{}; state={balance:finite(account.balance,START_BALANCE),position:payload.position&&typeof payload.position==='object'?payload.position:null,history:Array.isArray(payload.history)?payload.history.slice(-MAX_HISTORY):[]}; authoritative=true; cacheLocal(); render(); return payload; }
    catch(error){ authoritative=false; setNote(`Durable paper state unavailable: ${error.message}`); render(); return null; }
  }

  async function writeDurable(nextState,note) {
    if(syncBusy)return false; syncBusy=true; const previous=state; state=nextState;
    try { const response=await fetch(API,{method:'POST',cache:'no-store',headers:{'content-type':'application/json',accept:'application/json'},body:JSON.stringify(toDurablePayload())}); if(!response.ok)throw new Error((await response.json().catch(()=>({}))).message||`HTTP ${response.status}`); authoritative=true; cacheLocal(); if(note)setNote(note); render(); return true; }
    catch(error){ state=previous; authoritative=false; setNote(`Paper state was not committed: ${error.message}`); render(); return false; }
    finally { syncBusy=false; }
  }

  async function publishHeartbeat() { if (!authoritative || syncBusy || document.hidden) return; try { const response=await fetch(API,{method:'POST',cache:'no-store',headers:{'content-type':'application/json',accept:'application/json'},body:JSON.stringify({action:'heartbeat'})}); if(!response.ok)throw new Error(`HTTP ${response.status}`); } catch(error){ authoritative=false; setNote(`Runtime heartbeat unavailable: ${error.message}`); render(); } }

  function timeValue(value) { const n=Number(value); if(Number.isFinite(n))return n; const parsed=Date.parse(String(value||'')); return Number.isFinite(parsed)?parsed:NaN; }
  function normalizeBars(payload) { if(!Array.isArray(payload?.candles))return []; return payload.candles.map(raw=>({time:raw?.datetime??raw?.time,open:Number(raw?.open),high:Number(raw?.high),low:Number(raw?.low),close:Number(raw?.close)})).filter(bar=>Number.isFinite(timeValue(bar.time))&&[bar.open,bar.high,bar.low,bar.close].every(Number.isFinite)&&bar.high>=bar.low).sort((a,b)=>timeValue(a.time)-timeValue(b.time)); }
  async function getCompletedBars(symbol,timeframe) { const params=new URLSearchParams({symbol,timeframe}); const response=await fetch(`/api/signal?${params.toString()}`,{cache:'no-store'}),payload=await response.json(); if(!response.ok)throw new Error(payload?.message||payload?.error||`HTTP ${response.status}`); return normalizeBars(payload); }

  async function open(side) {
    if(!authoritative){await readDurable();if(!authoritative)return;} if(state.position)return setNote('Only one paper position is allowed at a time.');
    const symbol=currentSymbol(),timeframe=currentTimeframe(),entry=currentPrice(),quantity=Number($('qty')?.value),rawSl=$('sl')?.value?.trim(),rawTp=$('tp')?.value?.trim(),sl=rawSl?Number(rawSl):null,tp=rawTp?Number(rawTp):null;
    if(!Number.isFinite(entry))return setNote('Cannot open: no valid market quote.'); if(!Number.isFinite(quantity)||quantity<=0)return setNote('Rejected: quantity must be finite and > 0.');
    try{window.WebariaPaperEngine?.validateStops(side,entry,sl,tp);}catch(error){return setNote(`Rejected: ${error.message}`);} let bars; try{bars=await getCompletedBars(symbol,timeframe);}catch(error){return setNote(`Cannot open: ${error.message}`);} const latest=bars.at(-1); if(!latest)return setNote('Cannot open: no completed candle.');
    const next={...state,position:{symbol,timeframe,side,quantity,entry,sl:Number.isFinite(sl)?sl:null,tp:Number.isFinite(tp)?tp:null,opened_at:new Date().toISOString(),entry_bar_time:latest.time,entry_bar_close:latest.close,last_checked_bar_time:latest.time,execution_model:'completed-bar'}}; await writeDurable(next,`Opened ${side} ${quantity} ${symbol} · durable paper runtime`);
  }

  async function closeAt(exitPrice,reason,metadata={}) { const position=state.position;if(!position)return false;const price=Number(exitPrice);if(!Number.isFinite(price)||price<=0)return false;const realized=pnl(position,price),history=[...state.history,{id:`paper-${Date.now()}`,symbol:position.symbol,timeframe:position.timeframe,side:position.side,quantity:position.quantity,entry:position.entry,sl:position.sl,tp:position.tp,exit:price,pnl:realized,reason:reason||'manual close',opened_at:position.opened_at,closed_at:new Date().toISOString(),entry_bar_time:position.entry_bar_time,exit_bar_time:metadata.exitBarTime||null,exit_source:metadata.exitSource||'manual_quote',execution_model:position.execution_model||'completed-bar'}].slice(-MAX_HISTORY); return writeDurable({balance:state.balance+realized,position:null,history},`Closed ${reason||'manual close'} · realized ${realized>=0?'+':''}${realized.toFixed(2)} · durable paper runtime`); }
  async function close(reason){const position=state.position;if(!position)return;if(position.symbol!==currentSymbol())return setNote(`Switch to ${position.symbol} before closing.`);const price=currentPrice();if(!Number.isFinite(price))return setNote('Cannot close: no valid market quote.');await closeAt(price,reason||'manual close',{exitSource:'manual_quote'});}
  async function resetPaperAccount(){if(state.position)return setNote('Reset rejected while a position is open. Close it first.');await writeDurable({balance:START_BALANCE,position:null,history:[]},'Paper account reset · durable state');}

  async function monitorPosition(){ if(monitorBusy||!state.position||!authoritative)return; monitorBusy=true; try{const position=state.position,bars=await getCompletedBars(position.symbol,position.timeframe),anchor=timeValue(position.entry_bar_time),lastChecked=timeValue(position.last_checked_bar_time),cutoff=Number.isFinite(lastChecked)?Math.max(anchor,lastChecked):anchor; for(const bar of bars.filter(b=>timeValue(b.time)>cutoff)){const exit=window.WebariaPaperEngine?.barExit(position,bar);if(exit){await closeAt(exit.price,exit.reason,{exitBarTime:bar.time,exitSource:'completed_bar'});return;}position.last_checked_bar_time=bar.time;}if(bars.some(b=>timeValue(b.time)>cutoff))await writeDurable({...state,position:{...position}},null);}catch(error){setNote(`Completed-bar monitor error: ${error.message}`);}finally{monitorBusy=false;} }

  function bind(){ $('buy')?.addEventListener('click',e=>{e.preventDefault();void open('LONG');},true); $('sell')?.addEventListener('click',e=>{e.preventDefault();void open('SHORT');},true); $('close')?.addEventListener('click',e=>{e.preventDefault();void close('manual close');},true); $('resetPaper')?.addEventListener('click',e=>{e.preventDefault();void resetPaperAccount();},true); }

  bind(); render(); void readDurable(); setInterval(()=>{void monitorPosition();void readDurable();},POLL_MS); setInterval(()=>{void publishHeartbeat();},HEARTBEAT_MS); setInterval(render,1000);
})();
