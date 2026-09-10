/* Webaria realtime PAPER runtime.
 *
 * This browser runtime consumes completed candles from /api/signal, advances a
 * session lifecycle exactly once per candle, persists a restart checkpoint in
 * localStorage, uses stable client/idempotency keys, and never calls a real
 * broker. It is intentionally demo-only.
 */
(function (root) {
  'use strict';

  const STORAGE_KEY = 'webaria-paper-runtime-v1';
  const START_BALANCE = 10000;
  const MAX_EVENTS = 250;
  const POLL_MS = 10000;
  const STATES = Object.freeze({
    FLAT: 'FLAT', SIGNAL: 'SIGNAL', APPROVED: 'APPROVED', SUBMITTING: 'SUBMITTING',
    ACKNOWLEDGED: 'ACKNOWLEDGED', OPEN: 'OPEN', EXIT_PENDING: 'EXIT_PENDING',
    CLOSED: 'CLOSED', UNKNOWN: 'UNKNOWN', HALT: 'HALT'
  });

  const state = root.__ARIA_PAPER_RUNTIME__ || {
    running: false,
    halted: false,
    haltReason: '',
    lifecycle: STATES.FLAT,
    symbol: 'EUR/USD',
    timeframe: '5m',
    balance: START_BALANCE,
    realizedPnl: 0,
    position: null,
    pending: null,
    lastBarTime: null,
    lastProcessedBarTime: null,
    orders: [],
    events: [],
    seenOrderIds: {},
    failureMode: 'NONE'
  };
  root.__ARIA_PAPER_RUNTIME__ = state;

  function nowIso() { return new Date().toISOString(); }
  function asNumber(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
  function timeValue(v) { const n = Number(v); if (Number.isFinite(n)) return n; const t = Date.parse(String(v || '')); return Number.isFinite(t) ? t : NaN; }
  function stamp(v) { return new Date(timeValue(v)).toISOString().replace(/[-:.TZ]/g, '').slice(0, 17) + 'Z'; }

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object') return;
      Object.assign(state, saved);
      state.events = Array.isArray(state.events) ? state.events.slice(-MAX_EVENTS) : [];
      state.orders = Array.isArray(state.orders) ? state.orders : [];
      state.seenOrderIds = saved.seenOrderIds && typeof saved.seenOrderIds === 'object' ? saved.seenOrderIds : {};
      if (!Object.values(STATES).includes(state.lifecycle)) state.lifecycle = STATES.FLAT;
    } catch (_) {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      emit('CHECKPOINT_ERROR', 'HALT', error.message);
      state.halted = true;
      state.haltReason = 'unable to persist runtime checkpoint';
    }
  }

  function setLifecycle(next, reason) {
    const allowed = {
      FLAT: ['SIGNAL', 'HALT'], SIGNAL: ['APPROVED', 'FLAT', 'HALT'],
      APPROVED: ['SUBMITTING', 'HALT'], SUBMITTING: ['ACKNOWLEDGED', 'OPEN', 'UNKNOWN', 'FLAT', 'HALT'],
      ACKNOWLEDGED: ['OPEN', 'UNKNOWN', 'HALT'], OPEN: ['EXIT_PENDING', 'HALT'],
      EXIT_PENDING: ['CLOSED', 'OPEN', 'UNKNOWN', 'HALT'], CLOSED: ['FLAT', 'SIGNAL', 'HALT'],
      UNKNOWN: ['ACKNOWLEDGED', 'OPEN', 'CLOSED', 'FLAT', 'HALT'], HALT: ['HALT']
    };
    if (next === state.lifecycle) return true;
    if (!allowed[state.lifecycle]?.includes(next)) {
      halt(`invalid lifecycle transition ${state.lifecycle} -> ${next}`);
      return false;
    }
    state.lifecycle = next;
    emit('STATE', next, reason || 'transition');
    return true;
  }

  function emit(type, lifecycle, reason, extra) {
    state.events.push(Object.assign({
      id: `rt:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
      type, lifecycle, reason: String(reason || ''), timestamp: nowIso(),
      barTime: state.lastBarTime || null
    }, extra || {}));
    state.events = state.events.slice(-MAX_EVENTS);
    render();
  }

  function halt(reason) {
    state.halted = true;
    state.running = false;
    state.haltReason = reason;
    state.lifecycle = STATES.HALT;
    emit('HALT', STATES.HALT, reason);
    persist();
  }

  async function getFeed() {
    const qs = new URLSearchParams({ symbol: state.symbol, timeframe: state.timeframe });
    const response = await fetch(`/api/signal?${qs.toString()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`feed HTTP ${response.status}`);
    const payload = await response.json();
    if (payload?.error) throw new Error(payload.message || 'feed returned an error');
    const candles = Array.isArray(payload.candles) ? payload.candles.map(normalizeCandle).filter(Boolean).sort((a,b) => timeValue(a.time) - timeValue(b.time)) : [];
    if (!candles.length) throw new Error('feed returned no completed candles');
    const signal = payload.signal && typeof payload.signal === 'object' ? payload.signal : payload;
    return { candles, signal, raw: payload };
  }

  function normalizeCandle(raw) {
    const open = asNumber(raw?.open), high = asNumber(raw?.high), low = asNumber(raw?.low), close = asNumber(raw?.close);
    const time = raw?.datetime ?? raw?.time;
    if (![open, high, low, close].every(Number.isFinite) || !Number.isFinite(timeValue(time))) return null;
    if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) return null;
    return { time, open, high, low, close };
  }

  function normalizeSignal(raw) {
    const action = raw?.signal || raw?.action || 'WAIT';
    return {
      action: action === 'LONG' || action === 'SHORT' ? action : 'WAIT',
      state: raw?.state || 'APPROACH',
      reason: raw?.reason || 'no complete setup',
      entry: asNumber(raw?.entry_reference),
      stop: asNumber(raw?.stop_reference),
      score: asNumber(raw?.score),
      strategyVersion: raw?.strategy_version || 'unknown'
    };
  }

  function riskApproved(signal) {
    if (signal.action === 'WAIT') return false;
    if (!(signal.entry > 0) || !(signal.stop > 0) || signal.entry === signal.stop) return false;
    const riskDistance = Math.abs(signal.entry - signal.stop);
    const quantity = Math.floor((state.balance * 0.01 / riskDistance) * 1000) / 1000;
    return quantity > 0 ? { quantity } : false;
  }

  function conservativeExit(position, bar) {
    if (position.side === 'LONG') {
      if (position.sl != null && bar.low <= position.sl) return { price: position.sl, reason: 'stop loss' };
      if (position.tp != null && bar.high >= position.tp) return { price: position.tp, reason: 'take profit' };
    } else {
      if (position.sl != null && bar.high >= position.sl) return { price: position.sl, reason: 'stop loss' };
      if (position.tp != null && bar.low <= position.tp) return { price: position.tp, reason: 'take profit' };
    }
    return null;
  }

  function submitPaperOrder(side, quantity, price, barTime, kind) {
    const keyBase = `${kind}:${state.symbol}:${state.timeframe}:${stamp(barTime)}:${side}`;
    const clientOrderId = `${kind}-${state.symbol}-${stamp(barTime)}`;
    if (state.seenOrderIds[clientOrderId]) {
      emit('DUPLICATE_ORDER', state.lifecycle, 'idempotency key already exists', { clientOrderId });
      return state.seenOrderIds[clientOrderId];
    }

    setLifecycle(STATES.SUBMITTING, 'paper submission started');
    const order = {
      clientOrderId,
      idempotencyKey: keyBase,
      side,
      quantity,
      requestedPrice: price,
      filledQuantity: quantity,
      status: 'FILLED',
      createdAt: nowIso(),
      barTime,
      failureMode: state.failureMode
    };

    if (state.failureMode === 'DISCONNECT_BEFORE_SUBMIT') {
      order.status = 'UNKNOWN';
      state.seenOrderIds[clientOrderId] = order;
      state.orders.push(order);
      setLifecycle(STATES.UNKNOWN, 'simulated broker disconnect before submit');
      halt('broker disconnected before paper submit; outcome unknown');
      return order;
    }
    if (state.failureMode === 'REJECT') {
      order.status = 'REJECTED';
      order.filledQuantity = 0;
    } else if (state.failureMode === 'PARTIAL_FILL') {
      order.status = 'PARTIALLY_FILLED';
      order.filledQuantity = Math.floor(quantity * 0.5 * 1000) / 1000;
    }

    if (state.failureMode === 'TIMEOUT_AFTER_ACCEPT') {
      state.seenOrderIds[clientOrderId] = order;
      state.orders.push(order);
      emit('ORDER_UNKNOWN', STATES.UNKNOWN, 'timeout after broker acceptance', { clientOrderId });
      setLifecycle(STATES.UNKNOWN, 'response lost after paper broker accepted order');
      // Recovery is deterministic: inspect the durable simulated broker outcome.
      const recovered = state.orders.find(item => item.clientOrderId === clientOrderId);
      if (!recovered) { halt('timeout recovery could not locate paper order'); return order; }
      setLifecycle(recovered.status === 'FILLED' ? STATES.OPEN : STATES.FLAT, 'timeout outcome reconciled');
      order.status = recovered.status;
      if (order.status === 'FILLED') {
        order.filledQuantity = recovered.filledQuantity;
      }
      return order;
    }

    state.seenOrderIds[clientOrderId] = order;
    state.orders.push(order);
    if (order.status === 'REJECTED') {
      setLifecycle(STATES.FLAT, 'paper broker rejected order');
      emit('ORDER_REJECTED', STATES.FLAT, 'order rejected', { clientOrderId });
      return order;
    }
    if (order.status === 'PARTIALLY_FILLED') {
      halt('partial fill requires reconciliation before continuing');
      return order;
    }
    setLifecycle(STATES.ACKNOWLEDGED, 'paper broker acknowledged order');
    setLifecycle(STATES.OPEN, 'paper order fully filled');
    return order;
  }

  async function processCandle() {
    if (state.halted || !state.running) return;
    const feed = await getFeed();
    const bar = feed.candles.at(-1);
    state.lastBarTime = bar.time;
    if (state.lastProcessedBarTime && timeValue(bar.time) <= timeValue(state.lastProcessedBarTime)) {
      emit('NO_UPDATE', state.lifecycle, 'duplicate or old closed candle');
      return;
    }

    if (state.position) {
      const exit = conservativeExit(state.position, bar);
      if (exit) {
        setLifecycle(STATES.EXIT_PENDING, exit.reason);
        submitPaperOrder(state.position.side === 'LONG' ? 'SHORT' : 'LONG', state.position.quantity, exit.price, bar.time, 'exit');
        if (state.lifecycle === STATES.HALT) return;
        const pnl = (exit.price - state.position.entry) * (state.position.side === 'LONG' ? 1 : -1) * state.position.quantity;
        state.balance += pnl;
        state.realizedPnl += pnl;
        state.position = null;
        setLifecycle(STATES.CLOSED, exit.reason);
        setLifecycle(STATES.FLAT, 'position reconciled flat after exit');
        emit('POSITION_CLOSED', STATES.FLAT, exit.reason, { pnl });
      }
    }

    const signal = normalizeSignal(feed.signal);
    emit('SIGNAL', state.position ? STATES.OPEN : STATES.SIGNAL, signal.reason, { action: signal.action, score: signal.score });
    if (state.position || signal.action === 'WAIT') {
      state.lastProcessedBarTime = bar.time;
      persist();
      return;
    }

    setLifecycle(STATES.SIGNAL, signal.reason);
    const approved = riskApproved(signal);
    if (!approved) {
      setLifecycle(STATES.FLAT, 'risk/contract approval failed');
      state.lastProcessedBarTime = bar.time;
      persist();
      return;
    }
    setLifecycle(STATES.APPROVED, 'risk checks passed');
    const entry = submitPaperOrder(signal.action, approved.quantity, signal.entry, bar.time, 'entry');
    if (state.lifecycle === STATES.HALT || entry.status !== 'FILLED') {
      state.lastProcessedBarTime = bar.time;
      persist();
      return;
    }

    const risk = Math.abs(signal.entry - signal.stop);
    const tp = signal.action === 'LONG' ? signal.entry + (2 * risk) : signal.entry - (2 * risk);
    state.position = {
      symbol: state.symbol,
      timeframe: state.timeframe,
      side: signal.action,
      quantity: entry.filledQuantity,
      entry: signal.entry,
      sl: signal.stop,
      tp,
      entryBarTime: bar.time,
      orderId: entry.clientOrderId,
      execution: 'paper-completed-candle'
    };
    emit('POSITION_OPEN', STATES.OPEN, 'paper order filled and reconciled', { clientOrderId: entry.clientOrderId });
    state.lastProcessedBarTime = bar.time;
    persist();
  }

  function start() {
    state.running = true;
    state.halted = false;
    state.haltReason = '';
    if (state.lifecycle === STATES.HALT) state.lifecycle = STATES.FLAT;
    emit('RUNTIME_START', state.lifecycle, 'realtime paper runtime started');
    persist();
    void processCandle();
  }

  function stop() {
    state.running = false;
    emit('RUNTIME_STOP', state.lifecycle, 'runtime polling stopped');
    persist();
  }

  function recover() {
    state.running = false;
    try {
      const openOrders = state.orders.filter(o => ['UNKNOWN', 'SUBMITTING', 'ACKNOWLEDGED', 'PARTIALLY_FILLED'].includes(o.status));
      for (const order of openOrders) {
        if (state.failureMode === 'DISAPPEAR_POSITION' && order.status === 'FILLED') {
          halt(`simulated broker position disappeared for ${order.clientOrderId}`);
          return;
        }
        if (order.status === 'PARTIALLY_FILLED') {
          halt(`partial fill requires explicit reconciliation: ${order.clientOrderId}`);
          return;
        }
        if (order.status === 'UNKNOWN') {
          order.status = 'FILLED';
          emit('ORDER_RECOVERED', STATES.OPEN, 'unknown order reconciled from paper broker journal', { clientOrderId: order.clientOrderId });
        }
      }
      setLifecycle(state.position ? STATES.OPEN : STATES.FLAT, 'restart recovery reconciled');
      state.halted = false;
      state.haltReason = '';
      persist();
      emit('RECOVERY_COMPLETE', state.lifecycle, 'restart/crash recovery complete');
    } catch (error) {
      halt(`recovery failed: ${error.message}`);
    }
  }

  function setFailureMode(mode) {
    state.failureMode = mode;
    emit('FAILURE_MODE', state.lifecycle, mode);
    persist();
  }

  function reset() {
    if (state.position) return emit('RESET_BLOCKED', state.lifecycle, 'close the open paper position before reset');
    state.running = false; state.halted = false; state.haltReason = ''; state.lifecycle = STATES.FLAT;
    state.balance = START_BALANCE; state.realizedPnl = 0; state.position = null; state.pending = null;
    state.lastBarTime = null; state.lastProcessedBarTime = null; state.orders = []; state.events = []; state.seenOrderIds = {};
    persist(); render();
  }

  function configureFromDom() {
    const symbol = document.getElementById('paperRuntimeSymbol')?.value;
    const timeframe = document.getElementById('paperRuntimeTf')?.value;
    if (symbol) state.symbol = symbol;
    if (timeframe) state.timeframe = timeframe;
    persist();
  }

  function render() {
    const bind = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = String(value); };
    bind('rtMode', state.running ? 'RUNNING' : 'STOPPED');
    bind('rtState', state.lifecycle);
    bind('rtSymbol', `${state.symbol} · ${state.timeframe}`);
    bind('rtBalance', Number(state.balance).toFixed(2));
    bind('rtRealized', `${state.realizedPnl >= 0 ? '+' : ''}${Number(state.realizedPnl).toFixed(2)}`);
    bind('rtPosition', state.position ? `${state.position.side} ${state.position.quantity} @ ${state.position.entry}` : 'FLAT');
    bind('rtLastBar', state.lastBarTime || '—');
    bind('rtFailure', state.failureMode);
    bind('rtHalt', state.halted ? state.haltReason : '—');
    const eventNode = document.getElementById('rtEvents');
    if (eventNode) eventNode.innerHTML = state.events.slice().reverse().slice(0, 20).map(e => `<div class="rt-event"><b>${e.type}</b><span>${e.lifecycle}</span><small>${e.reason}</small></div>`).join('') || '<div class="rt-event"><small>No runtime events.</small></div>';
  }

  load();
  render();
  root.WebariaPaperRuntime = Object.freeze({ start, stop, recover, reset, processCandle, setFailureMode, configureFromDom, state, STATES });
  setInterval(() => { if (state.running) void processCandle().catch(error => halt(`runtime tick failed: ${error.message}`)); else render(); }, POLL_MS);
})(typeof window !== 'undefined' ? window : globalThis);
