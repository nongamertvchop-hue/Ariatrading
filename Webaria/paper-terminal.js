(function () {
  'use strict';

  const STORAGE_KEY = 'webaria-paper-account-v1';
  const START_BALANCE = 10000;
  const MAX_HISTORY = 100;
  const $ = id => document.getElementById(id);

  let state = loadState();

  function finitePositive(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : fallback;
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || typeof saved !== 'object') throw new Error('empty state');
      return {
        balance: finitePositive(saved.balance, START_BALANCE),
        position: saved.position && typeof saved.position === 'object' ? saved.position : null,
        history: Array.isArray(saved.history) ? saved.history.slice(-MAX_HISTORY) : []
      };
    } catch (_) {
      return { balance: START_BALANCE, position: null, history: [] };
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_) {
      setNote('Paper state could not be persisted in this browser.');
    }
  }

  function currentSymbol() {
    return $('symbol')?.value || 'EUR/USD';
  }

  function currentPrice() {
    const text = $('quote')?.textContent?.trim().replace(/,/g, '');
    const price = Number(text);
    return Number.isFinite(price) && price > 0 ? price : null;
  }

  function pnl(position, price) {
    if (!position || !Number.isFinite(price)) return 0;
    const direction = position.side === 'LONG' ? 1 : -1;
    return (price - position.entry) * direction * position.quantity;
  }

  function setNote(message) {
    const node = $('paperNote');
    if (node) node.textContent = message || 'Simulation only · execution NONE';
  }

  function renderHistory() {
    const node = $('paperHistory');
    if (!node) return;
    const rows = state.history.slice().reverse().slice(0, 5);
    if (!rows.length) {
      node.innerHTML = '<div class="paper-history-empty">No paper trades yet.</div>';
      return;
    }
    node.innerHTML = rows.map(t => {
      const result = Number(t.pnl);
      const cls = result > 0 ? 'up' : result < 0 ? 'down' : '';
      return `<div class="paper-trade"><span>${t.side} · ${t.symbol}</span><b class="${cls}">${result >= 0 ? '+' : ''}${result.toFixed(2)}</b><small>${t.reason}</small></div>`;
    }).join('');
  }

  function render() {
    const position = state.position;
    const price = currentPrice();
    const sameSymbol = position && position.symbol === currentSymbol();
    const unrealized = sameSymbol ? pnl(position, price) : 0;
    $('balance').textContent = state.balance.toFixed(2);
    $('equity').textContent = (state.balance + unrealized).toFixed(2);
    $('pos').textContent = position ? `${position.side} ${position.quantity}` : 'FLAT';
    $('entry').textContent = position ? formatPrice(position.entry) : '—';
    $('pnl').textContent = `${unrealized >= 0 ? '+' : ''}${unrealized.toFixed(2)}`;
    $('close').disabled = !position || !sameSymbol || !Number.isFinite(price);
    $('buy').disabled = !!position;
    $('sell').disabled = !!position;
    renderHistory();
  }

  function formatPrice(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(Math.abs(n) >= 20 ? 3 : 5) : '—';
  }

  function recordTrade(position, exitPrice, reason) {
    const realized = pnl(position, exitPrice);
    state.balance += realized;
    state.history.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      symbol: position.symbol,
      timeframe: position.timeframe,
      side: position.side,
      quantity: position.quantity,
      entry: position.entry,
      exit: exitPrice,
      pnl: realized,
      reason,
      opened_at: position.opened_at,
      closed_at: new Date().toISOString()
    });
    state.history = state.history.slice(-MAX_HISTORY);
    state.position = null;
    saveState();
    setNote(`Closed ${reason} · realized ${realized >= 0 ? '+' : ''}${realized.toFixed(2)} · demo only`);
    render();
  }

  function open(side) {
    if (state.position) {
      setNote('Only one paper position is allowed at a time.');
      return;
    }

    const symbol = currentSymbol();
    const entry = currentPrice();
    const quantity = Number($('qty')?.value);
    const rawSl = $('sl')?.value?.trim();
    const rawTp = $('tp')?.value?.trim();
    const sl = rawSl ? Number(rawSl) : null;
    const tp = rawTp ? Number(rawTp) : null;

    if (!Number.isFinite(entry)) {
      setNote('Cannot open paper trade: no valid quote.');
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setNote('Rejected: quantity must be finite and > 0.');
      return;
    }

    try {
      if (window.WebariaPaperEngine) {
        window.WebariaPaperEngine.validateStops(side, entry, sl, tp);
      }
    } catch (error) {
      setNote(`Rejected: ${error.message}`);
      return;
    }

    state.position = {
      symbol,
      timeframe: $('tf')?.value || '15m',
      side,
      quantity,
      entry,
      sl: Number.isFinite(sl) ? sl : null,
      tp: Number.isFinite(tp) ? tp : null,
      opened_at: new Date().toISOString()
    };
    saveState();
    setNote(`Opened ${side} ${quantity} ${symbol} · simulation only`);
    render();
  }

  function close(reason) {
    const position = state.position;
    if (!position) return;
    if (position.symbol !== currentSymbol()) {
      setNote(`Switch to ${position.symbol} before closing the position.`);
      return;
    }
    const price = currentPrice();
    if (!Number.isFinite(price)) {
      setNote('Cannot close paper trade: no valid quote.');
      return;
    }
    recordTrade(position, price, reason || 'manual close');
  }

  function checkStops() {
    const position = state.position;
    if (!position || position.symbol !== currentSymbol()) return;
    const price = currentPrice();
    if (!Number.isFinite(price)) return;

    if (position.side === 'LONG') {
      if (position.sl != null && price <= position.sl) return close('stop loss');
      if (position.tp != null && price >= position.tp) return close('take profit');
    } else if (position.side === 'SHORT') {
      if (position.sl != null && price >= position.sl) return close('stop loss');
      if (position.tp != null && price <= position.tp) return close('take profit');
    }
  }

  function intercept(handler) {
    return event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      handler();
    };
  }

  function bind() {
    $('buy')?.addEventListener('click', intercept(() => open('LONG')), true);
    $('sell')?.addEventListener('click', intercept(() => open('SHORT')), true);
    $('close')?.addEventListener('click', intercept(() => close('manual close')), true);
  }

  bind();
  render();
  setInterval(() => {
    checkStops();
    render();
  }, 1000);
  window.addEventListener('storage', event => {
    if (event.key === STORAGE_KEY) {
      state = loadState();
      render();
    }
  });
})();
