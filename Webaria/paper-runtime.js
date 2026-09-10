/* ARIA Paper Runtime — browser-safe paper/demo runtime only.
 * Closed-candle polling, checkpointed state, deterministic client identities,
 * P/L + equity + drawdown accounting, restart recovery, failure injection,
 * and a local 10,000-bar soak/replay diagnostic. No real broker calls.
 */
(function (root) {
  'use strict';

  const STORAGE_KEY = 'webaria-paper-runtime-v2';
  const START_BALANCE = 10000;
  const MAX_EVENTS = 300;
  const MAX_EQUITY_POINTS = 500;
  const POLL_MS = 10000;
  const RISK_FRACTION = 0.01;
  const STATES = Object.freeze({ FLAT:'FLAT', SIGNAL:'SIGNAL', APPROVED:'APPROVED', SUBMITTING:'SUBMITTING', ACKNOWLEDGED:'ACKNOWLEDGED', OPEN:'OPEN', EXIT_PENDING:'EXIT_PENDING', CLOSED:'CLOSED', UNKNOWN:'UNKNOWN', HALT:'HALT' });
  const FAILURES = Object.freeze({ NONE:'NONE', TIMEOUT_AFTER_ACCEPT:'TIMEOUT_AFTER_ACCEPT', DISCONNECT_BEFORE_SUBMIT:'DISCONNECT_BEFORE_SUBMIT', REJECT:'REJECT', PARTIAL_FILL:'PARTIAL_FILL', DISAPPEAR_POSITION:'DISAPPEAR_POSITION', CHECKPOINT_CORRUPTION:'CHECKPOINT_CORRUPTION' });

  const freshState = () => ({
    version: 2, running:false, halted:false, haltReason:'', lifecycle:STATES.FLAT,
    symbol:'EUR/USD', timeframe:'5m', balance:START_BALANCE, realizedPnl:0, unrealizedPnl:0,
    equity:START_BALANCE, peakEquity:START_BALANCE, drawdown:0, drawdownPct:0,
    tradeCount:0, winCount:0, lossCount:0, flatCount:0, winRate:0,
    position:null, pending:null, lastBarTime:null, lastProcessedBarTime:null,
    heartbeat:null, checkpointOk:true, orders:[], events:[], equityCurve:[], failureMode:FAILURES.NONE,
    soak:null
  });

  const state = root.__ARIA_PAPER_RUNTIME__ && root.__ARIA_PAPER_RUNTIME__.version === 2 ? root.__ARIA_PAPER_RUNTIME__ : freshState();
  root.__ARIA_PAPER_RUNTIME__ = state;
  let timer = null;

  function nowIso(){ return new Date().toISOString(); }
  function num(v){ const n=Number(v); return Number.isFinite(n)?n:null; }
  function timeValue(v){ const n=Number(v); if(Number.isFinite(n))return n; const t=Date.parse(String(v||'')); return Number.isFinite(t)?t:NaN; }
  function stamp(v){ const t=timeValue(v); return Number.isFinite(t)?new Date(t).toISOString().replace(/[-:.TZ]/g,'').slice(0,17)+'Z':'INVALID'; }
  function money(v){ return `${v>=0?'+':''}${Number(v||0).toFixed(2)}`; }
  function pct(v){ return `${Number(v||0).toFixed(2)}%`; }

  function load(){
    try{
      const raw=localStorage.getItem(STORAGE_KEY);
      if(!raw) return;
      const saved=JSON.parse(raw);
      if(!saved || typeof saved!=='object' || saved.version!==2) throw new Error('unsupported checkpoint version');
      Object.assign(state,saved);
      state.events=Array.isArray(state.events)?state.events.slice(-MAX_EVENTS):[];
      state.orders=Array.isArray(state.orders)?state.orders:[];
      state.equityCurve=Array.isArray(state.equityCurve)?state.equityCurve.slice(-MAX_EQUITY_POINTS):[];
      if(!Object.values(STATES).includes(state.lifecycle)) throw new Error('invalid lifecycle');
      state.checkpointOk=true;
    }catch(error){
      state.running=false; state.halted=true; state.lifecycle=STATES.HALT;
      state.haltReason=`checkpoint recovery failed: ${error.message}`;
      state.checkpointOk=false;
      emit('CHECKPOINT_CORRUPT',STATES.HALT,state.haltReason);
    }
  }

  function persist(){
    try{
      const payload={...state,events:state.events.slice(-MAX_EVENTS),orders:state.orders.slice(-MAX_EVENTS),equityCurve:state.equityCurve.slice(-MAX_EQUITY_POINTS)};
      localStorage.setItem(STORAGE_KEY,JSON.stringify(payload));
      state.checkpointOk=true;
    }catch(error){
      state.running=false; state.halted=true; state.lifecycle=STATES.HALT;
      state.haltReason='unable to persist runtime checkpoint'; state.checkpointOk=false;
      emit('CHECKPOINT_ERROR',STATES.HALT,error.message);
    }
  }

  function emit(type,lifecycle,reason,extra={}){
    state.events.push({id:`rt:${Date.now()}:${state.events.length+1}`,type,lifecycle,reason:String(reason||''),timestamp:nowIso(),barTime:state.lastBarTime||null,...extra});
    state.events=state.events.slice(-MAX_EVENTS);
    render();
  }

  function transition(next,reason){
    const allowed={
      FLAT:[STATES.SIGNAL,STATES.HALT], SIGNAL:[STATES.APPROVED,STATES.FLAT,STATES.HALT],
      APPROVED:[STATES.SUBMITTING,STATES.FLAT,STATES.HALT], SUBMITTING:[STATES.ACKNOWLEDGED,STATES.UNKNOWN,STATES.FLAT,STATES.HALT],
      ACKNOWLEDGED:[STATES.OPEN,STATES.UNKNOWN,STATES.HALT], OPEN:[STATES.EXIT_PENDING,STATES.HALT],
      EXIT_PENDING:[STATES.CLOSED,STATES.OPEN,STATES.UNKNOWN,STATES.HALT], CLOSED:[STATES.FLAT,STATES.SIGNAL,STATES.HALT],
      UNKNOWN:[STATES.OPEN,STATES.FLAT,STATES.HALT], HALT:[STATES.HALT]
    };
    if(next===state.lifecycle) return true;
    if(!(allowed[state.lifecycle]||[]).includes(next)) return halt(`invalid lifecycle transition ${state.lifecycle} -> ${next}`);
    state.lifecycle=next; emit('STATE',next,reason||'transition'); return true;
  }

  function halt(reason){
    state.running=false; state.halted=true; state.lifecycle=STATES.HALT; state.haltReason=String(reason||'halted');
    emit('HALT',STATES.HALT,state.haltReason); persist(); stopTimer();
    return false;
  }

  function normalizeCandle(raw){
    const open=num(raw?.open), high=num(raw?.high), low=num(raw?.low), close=num(raw?.close), time=raw?.datetime??raw?.time;
    if(![open,high,low,close].every(Number.isFinite) || !Number.isFinite(timeValue(time))) return null;
    if(high<Math.max(open,close)||low>Math.min(open,close)||high<low) return null;
    return {time,open,high,low,close};
  }
  function normalizeSignal(raw){
    const action=raw?.signal||raw?.action||'WAIT';
    return {action:action==='LONG'||action==='SHORT'?action:'WAIT',entry:num(raw?.entry_reference),stop:num(raw?.stop_reference),reason:raw?.reason||'no complete setup',score:num(raw?.score)};
  }

  async function getFeed(){
    const qs=new URLSearchParams({symbol:state.symbol,timeframe:state.timeframe});
    const response=await fetch(`/api/signal?${qs.toString()}`,{cache:'no-store'});
    if(!response.ok) throw new Error(`feed HTTP ${response.status}`);
    const payload=await response.json();
    if(payload?.error) throw new Error(payload.message||'feed returned an error');
    const candles=Array.isArray(payload.candles)?payload.candles.map(normalizeCandle).filter(Boolean).sort((a,b)=>timeValue(a.time)-timeValue(b.time)):[];
    if(!candles.length) throw new Error('feed returned no completed candles');
    return {bar:candles[candles.length-1],signal:normalizeSignal(payload.signal||payload)};
  }

  function markToMarket(price){
    if(!state.position){ state.unrealizedPnl=0; state.equity=state.balance; }
    else{
      const sign=state.position.side==='LONG'?1:-1;
      state.unrealizedPnl=(price-state.position.entry)*sign*state.position.quantity;
      state.equity=state.balance+state.unrealizedPnl;
    }
    state.peakEquity=Math.max(state.peakEquity,state.equity);
    state.drawdown=Math.max(0,state.peakEquity-state.equity);
    state.drawdownPct=state.peakEquity>0?(state.drawdown/state.peakEquity)*100:0;
    state.winRate=state.tradeCount?state.winCount/state.tradeCount*100:0;
  }

  function addEquityPoint(barTime){
    state.equityCurve.push({time:barTime,equity:Number(state.equity.toFixed(8)),balance:Number(state.balance.toFixed(8)),drawdown:Number(state.drawdown.toFixed(8))});
    state.equityCurve=state.equityCurve.slice(-MAX_EQUITY_POINTS);
  }

  function riskApproved(signal){
    if(signal.action==='WAIT'||!(signal.entry>0)||!(signal.stop>0)||signal.entry===signal.stop) return null;
    const distance=Math.abs(signal.entry-signal.stop); let quantity=Math.floor((state.balance*RISK_FRACTION/distance)*1000)/1000;
    if(!Number.isFinite(quantity)||quantity<=0) return null;
    return {quantity,distance};
  }

  function createOrder(side,quantity,price,barTime,kind){
    const clientOrderId=`${kind}-${state.symbol}-${state.timeframe}-${stamp(barTime)}`;
    if(state.orders.some(o=>o.clientOrderId===clientOrderId)){
      const existing=state.orders.find(o=>o.clientOrderId===clientOrderId); emit('DUPLICATE_ORDER',state.lifecycle,'idempotent request reused',{clientOrderId}); return existing;
    }
    const order={clientOrderId,idempotencyKey:`${kind}:${state.symbol}:${state.timeframe}:${stamp(barTime)}:${side}`,side,quantity,requestedPrice:price,filledQuantity:quantity,status:'FILLED',barTime,createdAt:nowIso(),failureMode:state.failureMode};
    state.orders.push(order);
    if(state.failureMode===FAILURES.REJECT){ order.status='REJECTED'; order.filledQuantity=0; }
    else if(state.failureMode===FAILURES.PARTIAL_FILL){ order.status='PARTIALLY_FILLED'; order.filledQuantity=Math.floor(quantity*0.5*1000)/1000; }
    if(state.failureMode===FAILURES.DISCONNECT_BEFORE_SUBMIT){ order.status='UNKNOWN'; state.pending=order; transition(STATES.UNKNOWN,'disconnect before paper submission'); halt('broker disconnected before submission; outcome unknown'); return order; }
    if(state.failureMode===FAILURES.TIMEOUT_AFTER_ACCEPT){ order.status='UNKNOWN'; state.pending=order; transition(STATES.UNKNOWN,'timeout after paper acceptance'); halt('response lost after acceptance; recovery required'); return order; }
    if(order.status==='REJECTED'){ emit('ORDER_REJECTED',STATES.FLAT,'paper broker rejected order',{clientOrderId}); return order; }
    if(order.status==='PARTIALLY_FILLED'){ state.pending=order; halt('partial fill requires explicit reconciliation'); return order; }
    return order;
  }

  function openPosition(signal,bar){
    const approval=riskApproved(signal); if(!approval) return false;
    transition(STATES.APPROVED,'paper risk checks passed'); transition(STATES.SUBMITTING,'paper submission started');
    const order=createOrder(signal.action,approval.quantity,signal.entry,bar.time,'entry');
    if(!order||order.status!=='FILLED') return false;
    transition(STATES.ACKNOWLEDGED,'paper broker acknowledged');
    state.position={symbol:state.symbol,timeframe:state.timeframe,side:signal.action,quantity:order.filledQuantity,entry:signal.entry,sl:signal.stop,tp:signal.action==='LONG'?signal.entry+2*approval.distance:signal.entry-2*approval.distance,entryBarTime:bar.time,orderId:order.clientOrderId};
    state.pending=null; transition(STATES.OPEN,'paper order filled and reconciled'); emit('POSITION_OPEN',STATES.OPEN,'paper position opened',{clientOrderId:order.clientOrderId});
    return true;
  }

  function checkExit(bar){
    if(!state.position) return null;
    if(state.position.side==='LONG'){
      if(bar.low<=state.position.sl) return {price:state.position.sl,reason:'stop loss'};
      if(bar.high>=state.position.tp) return {price:state.position.tp,reason:'take profit'};
    }else{
      if(bar.high>=state.position.sl) return {price:state.position.sl,reason:'stop loss'};
      if(bar.low<=state.position.tp) return {price:state.position.tp,reason:'take profit'};
    }
    return null;
  }

  function closePosition(price,barTime,reason){
    if(!state.position) return false;
    const position=state.position; transition(STATES.EXIT_PENDING,reason); transition(STATES.SUBMITTING,'paper exit submission started');
    const order=createOrder(position.side==='LONG'?'SHORT':'LONG',position.quantity,price,barTime,'exit');
    if(!order||order.status!=='FILLED'||state.halted) return false;
    const sign=position.side==='LONG'?1:-1; const pnl=(price-position.entry)*sign*position.quantity;
    state.balance+=pnl; state.realizedPnl+=pnl; state.unrealizedPnl=0; state.tradeCount+=1;
    if(pnl>0)state.winCount+=1; else if(pnl<0)state.lossCount+=1; else state.flatCount+=1;
    state.position=null; state.pending=null; state.equity=state.balance; state.peakEquity=Math.max(state.peakEquity,state.equity); state.drawdown=Math.max(0,state.peakEquity-state.equity); state.drawdownPct=state.peakEquity?state.drawdown/state.peakEquity*100:0;
    transition(STATES.ACKNOWLEDGED,'paper exit acknowledged'); transition(STATES.CLOSED,reason); transition(STATES.FLAT,'position reconciled flat'); emit('POSITION_CLOSED',STATES.FLAT,reason,{pnl});
    return true;
  }

  async function processCandle(){
    if(!state.running||state.halted) return;
    const feed=await getFeed(); const bar=feed.bar; state.heartbeat=nowIso();
    if(state.lastProcessedBarTime){ const current=timeValue(bar.time), last=timeValue(state.lastProcessedBarTime); if(current===last){markToMarket(bar.close); emit('NO_UPDATE',state.lifecycle,'duplicate/old completed candle'); persist(); return;} if(current<last){halt('out-of-order completed candle rejected'); return;} }
    state.lastBarTime=bar.time;
    markToMarket(bar.close);
    if(state.failureMode===FAILURES.DISAPPEAR_POSITION&&state.position){ halt('broker position disappeared during reconciliation'); return; }
    const exit=checkExit(bar); if(exit&&state.position){ if(!closePosition(exit.price,bar.time,exit.reason)) return; }
    if(!state.position){ emit('SIGNAL',STATES.SIGNAL,feed.signal.reason,{action:feed.signal.action,score:feed.signal.score}); if(feed.signal.action!=='WAIT'){transition(STATES.SIGNAL,feed.signal.reason); openPosition(feed.signal,bar);} }
    state.lastProcessedBarTime=bar.time; markToMarket(bar.close); addEquityPoint(bar.time); persist(); render();
  }

  function start(){
    if(state.halted){ emit('START_BLOCKED',STATES.HALT,state.haltReason); return; }
    state.running=true; state.halted=false; state.haltReason=''; transition(state.position?STATES.OPEN:STATES.FLAT,'runtime started'); emit('RUNTIME_START',state.lifecycle,'continuous realtime paper runtime started'); persist(); render();
    if(timer)clearInterval(timer); timer=setInterval(()=>void processCandle().catch(error=>halt(`runtime feed error: ${error.message}`)),POLL_MS); void processCandle().catch(error=>halt(`runtime feed error: ${error.message}`));
  }
  function stop(){ state.running=false; emit('RUNTIME_STOP',state.lifecycle,'runtime polling stopped'); persist(); stopTimer(); render(); }
  function stopTimer(){ if(timer){clearInterval(timer);timer=null;} }

  function recover(){
    stopTimer(); state.running=false;
    if(!state.checkpointOk){ state.halted=true; state.lifecycle=STATES.HALT; emit('RECOVERY_BLOCKED',STATES.HALT,'checkpoint integrity is not trusted'); return; }
    if(state.pending){ state.halted=true; state.lifecycle=STATES.HALT; state.haltReason='pending/unknown paper order requires explicit broker reconciliation'; emit('RECOVERY_BLOCKED',STATES.HALT,state.haltReason,{clientOrderId:state.pending.clientOrderId}); persist(); return; }
    state.halted=false; state.haltReason=''; state.lifecycle=state.position?STATES.OPEN:STATES.FLAT; state.checkpointOk=true; state.running=false; emit('RECOVERY_COMPLETE',state.lifecycle,'checkpoint restored; no unresolved execution state'); persist(); render();
  }

  function setFailureMode(mode){ state.failureMode=Object.values(FAILURES).includes(mode)?mode:FAILURES.NONE; emit('FAILURE_MODE',state.lifecycle,state.failureMode); persist(); }

  function reset(){
    if(state.position||state.pending) { emit('RESET_BLOCKED',state.lifecycle,'close/reconcile the open paper position before reset'); return; }
    stopTimer(); const replacement=freshState(); Object.keys(replacement).forEach(key=>state[key]=replacement[key]); persist(); render();
  }

  function configureFromDom(){ state.symbol=document.getElementById('paperRuntimeSymbol')?.value||state.symbol; state.timeframe=document.getElementById('paperRuntimeTf')?.value||state.timeframe; persist(); render(); }

  function runSoak(count=10000){
    const n=Math.max(1000,Math.floor(count)); let balance=START_BALANCE,peak=START_BALANCE,maxDD=0,realized=0,trades=0,wins=0; let position=null,price=100;
    for(let i=0;i<n;i++){
      const cycle=i%6, delta=[2,3,4,-2,-3,-4][cycle], open=price, close=price+delta, high=Math.max(open,close)+1, low=Math.min(open,close)-1; price=close;
      if(position){ if(position.side==='LONG'&&(low<=position.sl||high>=position.tp)){ const exit=low<=position.sl?position.sl:position.tp; const pnl=(exit-position.entry)*position.qty; balance+=pnl; realized+=pnl; trades++; if(pnl>0)wins++; position=null; } else if(position.side==='SHORT'&&(high>=position.sl||low<=position.tp)){ const exit=high>=position.sl?position.sl:position.tp; const pnl=(exit-position.entry)*-1*position.qty; balance+=pnl; realized+=pnl; trades++; if(pnl>0)wins++; position=null; } }
      if(!position&&cycle===0){ const entry=close, stop=close-5, qty=Math.floor((balance*RISK_FRACTION/(entry-stop))*1000)/1000; position={side:'LONG',entry,sl:stop,tp:entry+10,qty}; }
      const unrealized=position?(close-position.entry)*(position.side==='LONG'?1:-1)*position.qty:0, equity=balance+unrealized; peak=Math.max(peak,equity); maxDD=Math.max(maxDD,peak-equity);
    }
    state.soak={bars:n,trades,realizedPnl:Number(realized.toFixed(6)),finalBalance:Number(balance.toFixed(6)),maxDrawdown:Number(maxDD.toFixed(6)),winRate:trades?Number((wins/trades*100).toFixed(3)):0,deterministic:true,completedAt:nowIso()}; emit('SOAK_COMPLETE',state.lifecycle,`deterministic ${n.toLocaleString()}-bar replay complete`,{soak:state.soak}); persist(); render();
    return state.soak;
  }

  function exportSnapshot(){
    const payload=JSON.stringify({version:2,mode:'PAPER',exportedAt:nowIso(),state},null,2); const blob=new Blob([payload],{type:'application/json'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`aria-paper-runtime-${new Date().toISOString().replace(/[:.]/g,'-')}.json`; a.click(); URL.revokeObjectURL(url);
  }

  function render(){
    const byId=id=>document.getElementById(id); if(!byId('rtMode'))return;
    byId('rtMode').textContent=state.halted?'HALT':state.running?'RUNNING':'STOPPED'; byId('rtState').textContent=state.lifecycle; byId('rtSymbol').textContent=`${state.symbol} · ${state.timeframe}`; byId('rtLastBar').textContent=state.lastBarTime||'—';
    byId('rtBalance').textContent=Number(state.balance).toFixed(2); byId('rtRealized').textContent=money(state.realizedPnl); byId('rtUnrealized').textContent=money(state.unrealizedPnl); byId('rtEquity').textContent=Number(state.equity).toFixed(2); byId('rtPeak').textContent=Number(state.peakEquity).toFixed(2); byId('rtDrawdown').textContent=`${Number(state.drawdown).toFixed(2)} (${pct(state.drawdownPct)})`; byId('rtTrades').textContent=state.tradeCount; byId('rtWinRate').textContent=pct(state.winRate); byId('rtCheckpoint').textContent=state.checkpointOk?'OK':'UNTRUSTED'; byId('rtHeartbeat').textContent=state.heartbeat||'—'; byId('rtHalt').textContent=state.haltReason||'—'; byId('rtPosition').textContent=state.position?`${state.position.side} ${state.position.quantity} @ ${state.position.entry} · SL ${state.position.sl} · TP ${state.position.tp}`:'FLAT'; byId('rtFailure').textContent=state.failureMode; byId('rtSoak').textContent=state.soak?`${state.soak.bars.toLocaleString()} bars · ${state.soak.trades} trades · DD ${state.soak.maxDrawdown}`:'—';
    const events=byId('rtEvents'); events.innerHTML=state.events.slice().reverse().map(e=>`<div class="rt-event"><span>${e.type}</span><small>${e.timestamp} · ${e.lifecycle}</small><div>${escapeHtml(e.reason)}${e.pnl!=null?` · P/L ${money(e.pnl)}`:''}</div></div>`).join('');
    drawEquity();
    document.querySelectorAll('.step').forEach(node=>node.classList.toggle('active',node.dataset.state===state.lifecycle));
  }
  function escapeHtml(v){ return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  function drawEquity(){
    const canvas=document.getElementById('equityChart'); if(!canvas)return; const ctx=canvas.getContext('2d'); const w=canvas.width=canvas.clientWidth*devicePixelRatio||900*devicePixelRatio; const h=canvas.height=canvas.clientHeight*devicePixelRatio||220*devicePixelRatio; ctx.clearRect(0,0,w,h); const points=state.equityCurve; if(points.length<2)return; const vals=points.map(p=>p.equity); const min=Math.min(...vals), max=Math.max(...vals); const span=Math.max(1,max-min); ctx.beginPath(); points.forEach((p,i)=>{ const x=i/(points.length-1)*w; const y=h-((p.equity-min)/span)*(h-12*devicePixelRatio)-6*devicePixelRatio; if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y); }); ctx.stroke(); }

  load(); render();
  root.WebariaPaperRuntime={state,start,stop,recover,reset,setFailureMode,configureFromDom,runSoak,exportSnapshot,processCandle};
})(window);
