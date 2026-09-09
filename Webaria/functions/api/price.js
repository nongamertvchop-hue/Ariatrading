// Webaria Pages compatibility endpoint for the live-price panel.
// The Worker deployment already provides /api/price; this keeps the standalone
// Pages deployment functional as well.

const BASE_PRICE = Object.freeze({
  "EUR/USD": 1.08500,
  "GBP/USD": 1.27000,
  "USD/JPY": 147.500,
  "AUD/USD": 0.66000,
  "USD/CAD": 1.35500,
});

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

async function fetchRealPrice(symbol, apiKey) {
  const url = new URL("https://api.twelvedata.com/price");
  url.searchParams.set("symbol", symbol.replace("/", ""));
  url.searchParams.set("apikey", apiKey);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`provider HTTP ${response.status}`);
    const payload = await response.json();
    const price = Number(payload.price);
    if (!Number.isFinite(price)) throw new Error(payload.message || "invalid provider price");
    return { price, source: "twelve-data" };
  } finally {
    clearTimeout(timer);
  }
}

function fallbackPrice(symbol) {
  const base = BASE_PRICE[symbol] ?? 1.00000;
  const bucket = Math.floor(Date.now() / 10000);
  const movement = Math.sin(bucket * 0.31) * base * 0.00025;
  return Number((base + movement).toFixed(6));
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) return json({ error: "bad_request", message: "symbol must look like EUR/USD" }, 400);

  let price = fallbackPrice(symbol);
  let source = "pages-fallback";
  if (context.env?.TWELVE_DATA_API_KEY) {
    try {
      ({ price, source } = await fetchRealPrice(symbol, context.env.TWELVE_DATA_API_KEY));
    } catch (_) {
      // Keep the UI alive during provider/network failures. The response is
      // explicitly marked as fallback so it is never mistaken for live data.
    }
  }

  return json({
    symbol,
    price,
    source,
    generated_at: new Date().toISOString(),
    execution: "NONE",
  });
}
