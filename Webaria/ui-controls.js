/* Webaria UI interaction contract.
 * Every visible control must either mutate chart/UI state or explicitly report
 * why it cannot act. This layer never places broker orders.
 */
(function (root) {
  'use strict';

  const state = root.WebariaChartState;
  const $ = id => document.getElementById(id);

  function note(message) {
    const node = $('status');
    if (node) node.textContent = message;
  }

  function redraw() {
    if (typeof root.draw === 'function') root.draw();
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

  function refreshMarket() {
    if (typeof root.load === 'function') {
      void root.load();
      return;
    }
    if (root.WebariaLiveMarket && typeof root.WebariaLiveMarket.poll === 'function') {
      void root.WebariaLiveMarket.poll();
      return;
    }
    note('Refresh unavailable: market data controller is not loaded.');
  }

  function fitChart() {
    if (!state) {
      note('Fit unavailable: chart state is not initialized.');
      return;
    }
    state.offset = 0;
    state._userViewport = false;
    if (typeof root.fitVisibleBars === 'function') root.fitVisibleBars();
    redraw();
    note(`Chart fitted · ${state.symbol || 'market'} · ${state.tf || '15m'}`);
  }

  function toggleCrosshair(button) {
    if (!state) return;
    state.cross = !Boolean(state.cross);
    if (button) {
      button.classList.toggle('active', state.cross);
      button.setAttribute('aria-pressed', String(state.cross));
    }
    redraw();
    note(`Crosshair ${state.cross ? 'ON' : 'OFF'}`);
  }

  function resetView() {
    if (!state) return;
    state.offset = 0;
    state.dragging = false;
    state.draft = null;
    state.selectedDrawing = null;
    state._userViewport = false;
    if (typeof root.fitVisibleBars === 'function') root.fitVisibleBars();
    redraw();
    note('Chart view reset.');
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

  function setTool(tool, button) {
    if (!state) return;
    state.tool = tool;
    document.querySelectorAll('.tool[data-tool]').forEach(node => {
      node.classList.toggle('active', node === button);
      node.setAttribute('aria-pressed', String(node === button));
    });
    note(`Chart tool: ${tool}`);
    redraw();
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
    if (state && typeof state.watch === 'object') {
      const box = $('watch');
      if (box) box.textContent = 'Watchlist controller is unavailable; refresh market data.';
    }
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
    const fit = $('fit');
    const cross = $('cross');
    const refresh = $('refresh');
    const mobile = $('mobile');
    const reset = $('reset');

    fit?.addEventListener('click', fitChart);
    cross?.addEventListener('click', () => toggleCrosshair(cross));
    refresh?.addEventListener('click', refreshMarket);
    mobile?.addEventListener('click', () => togglePanel(mobile));
    reset?.addEventListener('click', resetView);

    document.querySelectorAll('.tool[data-tool]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.classList.contains('active')));
      button.addEventListener('click', () => setTool(button.dataset.tool || 'cursor', button));
    });

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
    cross?.setAttribute('aria-pressed', String(Boolean(state?.cross)));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind, { once: true });
  } else {
    bind();
  }

  root.WebariaUIControls = Object.freeze({ fitChart, refreshMarket, resetView, changeTimeframe });
})(typeof window !== 'undefined' ? window : globalThis);
