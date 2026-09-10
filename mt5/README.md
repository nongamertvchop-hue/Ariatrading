# Ariatrading MT5 bridge

`AriatradingBridge.mq5` is the broker-market ingress adapter for Ariatrading.
It sends normalized completed candles plus the current forming candle and price
to the Worker endpoint `/api/mt5/ingest`.

## MT5 configuration

1. Open MetaTrader 5 and compile `mt5/AriatradingBridge.mq5` as an Expert Advisor.
2. In **Tools → Options → Expert Advisors**, enable WebRequest and add the exact
   Worker base URL used by `BridgeUrl` (for example, `https://...workers.dev`).
3. Set `BridgeUrl` to the deployed `/api/mt5/ingest` endpoint.
4. Set `BridgeToken` to the same secret configured as the Worker `MT5_BRIDGE_TOKEN`.
   Do not commit the token to Git.
5. Attach the EA to any chart and keep Algo Trading enabled.

The EA itself does not contain strategy logic. The Worker validates the payload
and stores broker-market data behind the authenticated ingest boundary.

## Live execution

The Python live runtime now supports the explicit modes `ALERT_ONLY`, `DEMO`, and
`LIVE`. Before a LIVE order path is permitted, the runtime reconciles the connected
MT5 account mode and trading permissions. A DEMO/LIVE mismatch is rejected rather
than silently continuing.

The execution path remains:

`strategy -> market/risk gates -> idempotency journal -> MT5 executor -> broker`

An ambiguous broker response is never blindly retried.

## Important MT5 behavior

`WebRequest()` is synchronous and must be allowed explicitly in the terminal. It
also does not execute inside the Strategy Tester, so network integration tests
must use mocked requests or a running terminal rather than relying on tester
network access.
