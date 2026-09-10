// Webaria Pages compatibility endpoint for the live-price panel.
// Live market data is required. This endpoint never fabricates a quote.
// The Worker deployment provides the canonical /api/price; this keeps the
// standalone Pages deployment consistent with that contract.

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
    if (payload.status === "error") throw new Error(payload.message || "provider error");

    const price = Number(payload.price);
    if (!Number.isFinite(price)) throw new Error("invalid provider price");
    return { price, source: "twelve-data" };
  } finally {
    clearTimeout(timer);
  }
}

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const symbol = (url.searchParams.get("symbol") || "EUR/USD").trim().toUpperCase();
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(symbol)) {
    return json({
      error: "bad_request",
      message: "symbol must look like EUR/USD",
    }, 400);
  }

  const apiKey = context.env?.TWELVE_DATA_API_KEY;
  if (!apiKey) {
    return json({
      error: "live_data_unavailable",
      message: "TWELVE_DATA_API_KEY is not configured",
      symbol,
      source: "unavailable",
      execution: "NONE",
    }, 503);
  }

  try {
    const quote = await fetchRealPrice(symbol, apiKey);
    return json({
      symbol,
      ...quote,
      generated_at: new Date().toISOString(),
      execution: "NONE",
    });
  } catch (error) {
    return json({
      error: "live_data_unavailable",
      message: error?.message || "market data provider unavailable",
      symbol,
      source: "unavailable",
      execution: "NONE",
    }, 503);
  }
}
