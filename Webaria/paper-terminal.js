(function () {
  'use strict';

  const STORAGE_KEY = 'webaria-paper-account-v1';
  const START_BALANCE = 10000;
  const MAX_HISTORY = 100;
  const BAR_POLL_MS = 30000;
  const $ = id => document.getElementById(id);

  let state = loadState();
  let monitorBusy = false;

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

  function currentTimeframe() {
    return $('tf')?.value || '15m';
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
    if (node) node.textContent = message || 'Simulation only · execution NONE · paper orders never reach a broker';
  }

  function renderHistory() {
    const node = $('history') || $('paperHistory');
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

  function renderMetrics() {
    const node = $('paperMetrics');
    if (!node) return;

    const trades = state.history.filter(t => Number.isFinite(Number(t.pnl)));
    const wins = trades.filter(t => Number(t.pnl) > 0);
    const losses = trades.filter(t => Number(t.pnl) < 0);
    const netPnl = trades.reduce((sum, t) => sum + Number(t.pnl), 0);
    const grossProfit = wins.reduce((sum, t) => sum + Number(t.pnl), 0);
    const grossLoss = Math.abs(losses.reduce((sum, t) => sum + Number(t.pnl), 0));
    const winRate = trades.length ? (wins.length / trades.length) * 100 : 0;
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : null);

    let runningBalance = START_BALANCE;
    let peakBalance = START_BALANCE;
    let maxDrawdown = 0;
    for (const trade of state.history) {
      const result = Number(trade.pnl);
      if (!Number.isFinite(result)) continue;
      runningBalance += result;
      peakBalance = Math.max(peakBalance, runningBalance);
      maxDrawdown = Math.max(maxDrawdown, peakBalance - runningBalance);
    }

    const rValues = trades.map(t => {
      const entry = Number(t.entry);
      const stop = Number(t.sl);
      const qty = Number(t.quantity);
      const result = Number(t.pnl);
      if (![entry, stop, qty, result].every(Number.isFinite) || qty <= 0 || entry === stop) return null;
      const risk = Math.abs(entry - stop) * qty;
      return risk > 0 ? result / risk : null;
    }).filter(Number.isFinite);
    const avgR = rValues.length ? rValues.reduce((sum, value) => sum + value, 0) / rValues.length : null;

    const format = value => Number.isFinite(value) ? value.toFixed(2) : '—';
    const pf = profitFactor === Infinity ? '∞' : format(profitFactor);

    node.innerHTML = `
      <div class="metric"><span>Trades</span><b>${trades.length}</b></div>
      <div class="metric"><span>Win rate</span><b>${winRate.toFixed(1)}%</b></div>
      <div class="metric"><span>Net P/L</span><b>${netPnl >= 0 ? '+' : ''}${format(netPnl)}</b></div>
      <div class="metric"><span>Profit factor</span><b>${pf}</b></div>
      <div class="metric"><span>Max drawdown</span><b>${format(maxDrawdown)}</b></div>
      <div class="metric"><span>Avg R</span><b>${avgR == null ? '—' : `${avgR >= 0 ? '+' : ''}${avgR.toFixed(2)}R`}</b></div>
    `;
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
    renderMetrics();
    renderHistory();
  }

  function formatPrice(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(Math.abs(n) >= 20 ? 3 : 5) : '—';
  }

  function timeValue(value) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric;
    const parsed = Date.parse(String(value || ''));
    return Number.isFinite(parsed) ? parsed : NaN;
  }

  function normalizeBars(payload) {
    if (!Array.isArray(payload?.candles)) return [];
    return payload.candles.map(raw => ({
      time: raw?.datetime ?? raw?.time,
      open: Number(raw?.open),
      high: Number(raw?.high),
      low: Number(raw?.low),
      close: Number(raw?.close)
    })).filter(bar =>
      Number.isFinite(timeValue(bar.time)) &&
      Number.isFinite(bar.open) &&
      Number.isFinite(bar.high) &&
      Number.isFinite(bar.low) &&
      Number.isFinite(bar.close)
    ).sort((a, b) => timeValue(a.time) - timeValue(b.time));
  }

  async function getCompletedBars(symbol, timeframe) {
    const params = new URLSearchParams({ symbol, timeframe });
    const response = await fetch(`/api/signal?${params.toString()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`signal endpoint HTTP ${response.status}`);
    const payload = await response.json();
    if (payload?.error) throw new Error(payload.message || 'signal endpoint error');
    return normalizeBars(payload);
  }

  function recordTrade(position, exitPrice, reason, metadata = {}) {
    const realized = pnl(position, exitPrice);
    state.balance += realized;
    state.history.push({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      symbol: position.symbol,
      timeframe: position.timeframe,
      side: position.side,
      quantity: position.quantity,
      entry: position.entry,
      sl: position.sl ?? null,
      tp: position.tp ?? null,
      exit: exitPrice,
      pnl: realized,
      reason,
      opened_at: position.opened_at,
      closed_at: new Date().toISOString(),
      entry_bar_time: position.entry_bar_time || null,
      exit_bar_time: metadata.exitBarTime || null,
      exit_source: metadata.exitSource || 'manual_quote',
      execution_model: position.execution_model || 'manual_quote'
    });
    state.history = state.history.slice(-MAX_HISTORY);
    state.position = null;
    saveState();
    setNote(`Closed ${reason} · realized ${realized >= 0 ? '+' : ''}${realized.toFixed(2)} · demo only`);
    render();
  }

  async function open(side) {
    if (state.position) {
      setNote('Only one paper position is allowed at a time.');
      return;
    }

    const symbol = currentSymbol();
    const timeframe = currentTimeframe();
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

    let bars;
    try {
      bars = await getCompletedBars(symbol, timeframe);
    } catch (error) {
      setNote(`Cannot open paper trade: ${error.message}`);
      return;
    }

    const latestBar = bars[bars.length - 1];
    if (!latestBar) {
      setNote('Cannot open paper trade: no completed candle is available.');
      return;
    }

    state.position = {
      symbol,
      timeframe,
      side,
      quantity,
      entry,
      sl: Number.isFinite(sl) ? sl : null,
      tp: Number.isFinite(tp) ? tp : null,
      opened_at: new Date().toISOString(),
      entry_bar_time: latestBar.time,
      entry_bar_close: latestBar.close,
      last_checked_bar_time: latestBar.time,
      execution_model: 'completed-bar'
    };
    saveState();
    setNote(`Opened ${side} ${quantity} ${symbol} · entry anchored after completed ${timeframe} bar · demo only`);
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
    recordTrade(position, price, reason || 'manual close', { exitSource: 'manual_quote' });
  }

  function resetPaperAccount() {
    if (state.position) {
      setNote('Reset rejected while a paper position is open. Close the position first.');
      return;
    }
    state = { balance: START_BALANCE, position: null, history: [] };
    saveState();
    setNote('Paper account reset · simulation only · execution NONE · paper orders never reach a broker');
    render();
  }

  async function monitorPosition() {
    if (monitorBusy || !state.position) return;
    monitorBusy = true;

    try {
      const position = state.position;
      const bars = await getCompletedBars(position.symbol, position.timeframe);
      const latestBar = bars[bars.length - 1];
      if (!latestBar) return;

      const anchor = timeValue(position.entry_bar_time);
      if (!Number.isFinite(anchor)) {
        // Legacy positions are migrated without evaluating any old bar.
        position.entry_bar_time = latestBar.time;
        position.entry_bar_close = latestBar.close;
        position.last_checked_bar_time = latestBar.time;
        position.execution_model = 'completed-bar';
        saveState();
        setNote('Migrated existing paper position to completed-bar monitoring.');
        return;
      }

      const lastChecked = timeValue(position.last_checked_bar_time);
      const cutoff = Number.isFinite(lastChecked) ? Math.max(anchor, lastChecked) : anchor;
      const candidates = bars.filter(bar => timeValue(bar.time) > cutoff);

      for (const bar of candidates) {
        const exit = window.WebariaPaperEngine?.barExit(position, bar);
        if (exit) {
          recordTrade(position, exit.price, exit.reason, {
            exitBarTime: bar.time,
            exitSource: 'completed_bar'
          });
          return;
        }
        position.last_checked_bar_time = bar.time;
      }

      if (candidates.length) saveState();
    } catch (error) {
      setNote(`Bar monitor error: ${error.message}. Position remains open.`);
    } finally {
      monitorBusy = false;
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
    $('buy')?.addEventListener('click', intercept(() => { void open('LONG'); }), true);
    $('sell')?.addEventListener('click', intercept(() => { void open('SHORT'); }), true);
    $('close')?.addEventListener('click', intercept(() => close('manual close')), true);
    $('resetPaper')?.addEventListener('click', intercept(resetPaperAccount), true);
  }

  bind();
  render();
  void monitorPosition();
  setInterval(() => {
    void monitorPosition();
    render();
  }, BAR_POLL_MS);
  setInterval(render, 1000);

  window.addEventListener('storage', event => {
    if (event.key === STORAGE_KEY) {
      state = loadState();
      render();
    }
  });
})();
