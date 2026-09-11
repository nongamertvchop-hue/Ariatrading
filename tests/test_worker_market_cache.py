from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "worker" / "entry.js"
WRANGLER = ROOT / "wrangler.toml"


def test_worker_gateway_caches_slow_endpoints_but_never_caches_realtime_signal_or_market_feed():
    source = ENTRY.read_text(encoding="utf-8")
    for marker in (
        'import app from "./index.js"',
        '"/api/price":10000',
        '"/api/live-candle":10000',
        '"/api/market"',
        '"STALE"',
        'responseCache',
        'app.fetch(request,env,ctx)',
    ):
        assert marker in source, f"missing market cache gateway marker: {marker}"

    fresh_line = next(line for line in source.splitlines() if line.startswith("const FRESH_TTL_MS"))
    stale_line = next(line for line in source.splitlines() if line.startswith("const STALE_TTL_MS"))
    assert '"/api/signal":' not in fresh_line
    assert '"/api/signal":' not in stale_line
    assert '"/api/market":' not in fresh_line
    assert '"/api/market":' not in stale_line


def test_worker_signal_handler_explicitly_disables_http_caching():
    source = (ROOT / "worker" / "signal_parity_v2.js").read_text(encoding="utf-8")
    assert '"cache-control": "no-store"' in source


def test_mt5_market_polling_has_dedicated_rate_limit_and_bypasses_generic_soft_ban():
    source = ENTRY.read_text(encoding="utf-8")
    assert "const MARKET_RATE_MAX=120;" in source
    assert "function marketRateLimit(request)" in source
    assert 'url.pathname!=="/api/market"' in source
    assert 'if(url.pathname==="/api/market"){const limited=marketRateLimit(request);if(limited)return limited;}' in source


def test_wranger_uses_cache_gateway_as_worker_entrypoint():
    config = WRANGLER.read_text(encoding="utf-8")
    assert 'main = "./worker/entry.js"' in config
    assert 'run_worker_first = ["/api/*"]' in config
