/* Webaria UI interaction contract.
 * Every visible control must either mutate chart/UI state or explicitly report
 * why it cannot act. This layer never places broker orders.
 *
 * Chart data controls (symbol, timeframe, Fit, Refresh, Crosshair, Reset and
 * drawing tools) are owned by trading.js. Keeping a single owner prevents
 * double handlers, duplicate requests and toggle actions cancelling themselves.
 */
(function (root) {
  'use strict';

  const state = root.WebariaChartState;
  const $ = id => document.getElementById(id);

  function note(message) {
    const node = $('status');
    if (node) node.textContent = message;
  }

  function changeTimeframe(tf) {
    const select = $('tf');
    if (!select) return;
    if (![...select.options].some(option => option.value === tf)) {
      note(`Unsupported timeframe: ${tf}`);
      return;
    }
    select.value = tf;
    select.dispatchEvent(new Event('change', { bubbles: true }));
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

  function bindTabs() {
    const tabs = document.querySelectorAll('.tabs button');
    if (tabs.length < 2) return;
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

  function bind() {
    const mobile = $('mobile');

    mobile?.addEventListener('click', () => togglePanel(mobile));

    document.querySelectorAll('.bottom [data-tf]').forEach(button => {
      button.addEventListener('click', () => {
        changeTimeframe(button.dataset.tf || '15m');
        document.querySelectorAll('.bottom [data-tf]').forEach(node => {
          node.classList.toggle('active', node === button);
        });
      });
    });

    $('brand')?.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      note('Webaria terminal · chart controller ready.');
    });

    bindTabs();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind, { once: true });
  } else {
    bind();
  }

  root.WebariaUIControls = Object.freeze({ changeTimeframe });
})(typeof window !== 'undefined' ? window : globalThis);
