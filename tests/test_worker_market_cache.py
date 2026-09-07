from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "worker" / "entry.js"
WRANGLER = ROOT / "wrangler.toml"


def test_worker_gateway_wraps_existing_worker_and_caches_market_endpoints():
    source = ENTRY.read_text(encoding="utf-8")
    for marker in (
        'import app from "./index.js"',
        '"/api/price": 10_000',
        '"/api/signal": 30_000',
        '"/api/live-candle": 10_000',
        '"STALE"',
        'responseCache',
        'app.fetch(request, env, ctx)',
    ):
        assert marker in source, f"missing market cache gateway marker: {marker}"


def test_wranger_uses_cache_gateway_as_worker_entrypoint():
    config = WRANGLER.read_text(encoding="utf-8")
    assert 'main = "./worker/entry.js"' in config
    assert 'run_worker_first = ["/api/*"]' in config
