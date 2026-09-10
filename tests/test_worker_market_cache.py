from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "worker" / "entry.js"
WRANGLER = ROOT / "wrangler.toml"


def test_worker_gateway_caches_slow_endpoints_but_never_caches_realtime_market_feed():
    source = ENTRY.read_text(encoding="utf-8")
    for marker in (
        'import app from "./index.js"',
        '"/api/price":10000',
        '"/api/signal":30000',
        '"/api/live-candle":10000',
        '"/api/market"',
        '"STALE"',
        'responseCache',
        'app.fetch(request,env,ctx)',
    ):
        assert marker in source, f"missing market cache gateway marker: {marker}"

    fresh_line = next(line for line in source.splitlines() if line.startswith("const FRESH_TTL_MS"))
    stale_line = next(line for line in source.splitlines() if line.startswith("const STALE_TTL_MS"))
    assert '"/api/market":' not in fresh_line
    assert '"/api/market":' not in stale_line


def test_wranger_uses_cache_gateway_as_worker_entrypoint():
    config = WRANGLER.read_text(encoding="utf-8")
    assert 'main = "./worker/entry.js"' in config
    assert 'run_worker_first = ["/api/*"]' in config
