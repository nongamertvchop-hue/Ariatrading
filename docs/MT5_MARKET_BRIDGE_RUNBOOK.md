# MT5 Market Bridge — first real-data run

This runbook is for the first end-to-end market-data check. It is deliberately read-only: no broker order is submitted by the bridge.

## 1. Windows host requirements

- MetaTrader 5 is installed and logged into the intended account.
- Python 3.12 is installed.
- The repository is checked out locally.
- Install the realtime dependency set:

```powershell
python -m pip install -r requirements-realtime.txt
```

## 2. Create a bridge token

Generate a long random token locally and keep it out of Git:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it for the current shell:

```powershell
$env:MT5_MARKET_BRIDGE_TOKEN = "PASTE_GENERATED_TOKEN_HERE"
```

Optional terminal path:

```powershell
$env:MT5_TERMINAL_PATH = "C:\Program Files\MetaTrader 5\terminal64.exe"
```

## 3. Start the read-only bridge

```powershell
python -m live.mt5_market_bridge
```

Default listener:

`http://127.0.0.1:8787/market`

The bridge reads completed candles from MT5 with start position `1`, reads the current candle separately with start position `0`, and exposes bid/ask plus midpoint price.

## 4. Test the bridge locally

In another PowerShell window:

```powershell
$headers = @{ Authorization = "Bearer $env:MT5_MARKET_BRIDGE_TOKEN" }
Invoke-RestMethod -Headers $headers -Uri "http://127.0.0.1:8787/market?symbol=EURUSD&timeframe=5m&count=100"
```

A healthy response must contain:

- `source: "mt5"`
- `execution: "NONE"`
- at least 20 completed candles
- a separate `live_candle`
- positive `price`
- `tick.bid` and `tick.ask`

## 5. Connect Webaria

The hosted Webaria Worker cannot directly reach `127.0.0.1` on the Windows PC. For the hosted page, expose the bridge through an HTTPS reverse proxy/private tunnel and set the Cloudflare Worker secrets/configuration:

- `MT5_RUNTIME_API_URL` → the HTTPS base URL of the bridge host
- `RUNTIME_API_TOKEN` → the same bridge token

The browser path is then:

`MT5 -> bridge /market -> Webaria /api/market -> Webaria chart`

and:

`MT5 -> bridge /market -> Webaria /api/signal -> strategy`

The strategy endpoint must remain MT5-backed and must fail closed when the broker feed is unavailable.

## 6. Acceptance test

Do not call the system `LIVE` until all of these are simultaneously true:

1. MT5 terminal shows a connected market and current quote.
2. `/market` returns `source: "mt5"` and fresh data.
3. Webaria `/api/market` returns the same symbol/timeframe and broker-sourced candles.
4. The web chart's latest completed candle matches the MT5 terminal's latest completed candle for that timeframe.
5. The displayed quote is consistent with the bridge bid/ask.
6. `/api/signal` returns `source: "mt5"` and uses those same candles.
7. Disconnecting MT5 causes the web to show `MT5 DATA UNAVAILABLE` rather than silently switching providers.

This proves the market-data path. It does not by itself prove strategy profitability or approve real-money execution.
