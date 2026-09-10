/* Webaria UI interaction contract.
 * Every visible control must either mutate chart/UI state or explicitly report
 * why it cannot act. This layer never places broker orders.
 *
 * Chart data controls are routed through the MT5 live bridge when available.
 * Capture listeners prevent trading.js legacy /api/signal handlers from
 * racing the canonical /api/market + /api/strategy flow.
 */
(function (root) {
  'use strict';

  const state = root.WebariaChartState;
  const $ = id => document.getElementById(id);

  function note(message) {
    const node = $('status');
    if (node) node.textContent = message;
  }

  function pollLiveMarket() {
    if (root.WebariaLiveMarket && typeof root.WebariaLiveMarket.poll === 'function') {
      void root.WebariaLiveMarket.poll();
      return true;
    }
    return false;
  }

  function changeMarket(symbol, timeframe) {
    if (!state) return;
    if (symbol) {
      state.symbol = symbol;
      const select = $('symbol');
      if (select) select.value = symbol;
    }
    if (timeframe) {
      state.tf = timeframe;
      const select = $('tf');
      if (select) select.value = timeframe;
    }
    state.offset = 0;
    state._userViewport = false;
    if (!pollLiveMarket() && typeof root.load === 'function') void root.load();
  }

  function changeTimeframe(tf) {
    const select = $('tf');
    if (!select) return;
    if (![...select.options].some(option => option.value === tf)) {
      note(`Unsupported timeframe: ${tf}`);
      return;
    }
    changeMarket($('symbol')?.value || state?.symbol, tf);
  }

  function togglePanel(button) {
    const panel = $('right');
    if (!panel) return;
    const open = panel.classList.toggle('open');
    if (button) {
      button.setAttribute('aria-expanded', String(open));
      button.textContent = open ? 'Panel' : 'Show Panel';
    }
  }

  function renderDetails() {
    const box = $('watch');
    if (!box || !state) return;
    const signal = state.signal || {};
    const price = Number(state.price);
    box.innerHTML = [
      `<div class="watch-detail"><span>Symbol</span><b>${String(state.symbol || '—')}</b></div>`,
      `<div class="watch-detail"><span>Timeframe</span><b>${String(state.tf || '—')}</b></div>`,
      `<div class="watch-detail"><span>Source</span><b>${String(signal.source || '—')}</b></div>`,
      `<div class="watch-detail"><span>Price</span><b>${Number.isFinite(price) ? price : '—'}</b></div>`,
      `<div class="watch-detail"><span>Strategy state</span><b>${String(signal.state || '—')}</b></div>`,
      `<div class="watch-detail"><span>Signal</span><b>${String(signal.signal || signal.direction || 'WAIT')}</b></div>`
    ].join('');
  }

  function restoreWatchlist() {
    if (typeof root.updateWatch === 'function') {
      void root.updateWatch();
      return;
    }
    const box = $('watch');
    if (box) box.textContent = 'Watchlist controller is unavailable; refresh market data.';
  }

  function bind() {
    const mobile = $('mobile');
    mobile?.addEventListener('click', () => togglePanel(mobile));

    const symbol = $('symbol');
    symbol?.addEventListener('change', event => {
      event.stopImmediatePropagation();
      changeMarket(symbol.value, $('tf')?.value || '15m');
    }, true);

    const timeframe = $('tf');
    timeframe?.addEventListener('change', event => {
      event.stopImmediatePropagation();
      changeMarket(symbol?.value || state?.symbol || 'EUR/USD', timeframe.value);
    }, true);

    document.querySelectorAll('.bottom [data-tf]').forEach(button => {
      button.addEventListener('click', event => {
        event.stopImmediatePropagation();
        changeTimeframe(button.dataset.tf || '15m');
        document.querySelectorAll('.bottom [data-tf]').forEach(node => {
          node.classList.toggle('active', node === button);
        });
      }, true);
    });

    $('watch')?.addEventListener('click', event => {
      const row = event.target.closest?.('[data-symbol]');
      if (!row) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      changeMarket(row.dataset.symbol, $('tf')?.value || state?.tf || '15m');
    }, true);

    $('brand')?.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      note('Webaria terminal · chart controller ready.');
    });

    const tabs = document.querySelectorAll('.tabs button');
    if (tabs.length >= 2) {
      tabs[0].addEventListener('click', () => {
        tabs[0].classList.add('active');
        tabs[1].classList.remove('active');
        restoreWatchlist();
      });
      tabs[1].addEventListener('click', () => {
        tabs[1].classList.add('active');
        tabs[0].classList.remove('active');
        renderDetails();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind, { once: true });
  } else {
    bind();
  }

  root.WebariaUIControls = Object.freeze({ changeMarket, changeTimeframe });
})(typeof window !== 'undefined' ? window : globalThis);
