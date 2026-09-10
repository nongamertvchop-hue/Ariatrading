#property strict
#property version   "1.0"
#property description "Ariatrading MT5 market-data bridge. Demo/paper market data only; never sends trading orders."

input string BridgeUrl = "https://YOUR-WORKER.workers.dev/api/mt5/ingest";
input string BridgeToken = "SET_IN_MT5_TERMINAL";
input string WebSymbol = "EUR/USD";
input int HistoryBars = 200;
input int PollSeconds = 1;
input int HttpTimeoutMs = 5000;

struct TfConfig { ENUM_TIMEFRAMES tf; string name; };
TfConfig Tfs[7] = {
   {PERIOD_M1,  "1m"},
   {PERIOD_M5,  "5m"},
   {PERIOD_M15, "15m"},
   {PERIOD_M30, "30m"},
   {PERIOD_H1,  "1h"},
   {PERIOD_H4,  "4h"},
   {PERIOD_D1,  "1D"}
};

typedef char byte_array[];

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   return value;
}

string CandleJson(MqlRates &r)
{
   return StringFormat("{\"time\":%I64d,\"open\":%.10f,\"high\":%.10f,\"low\":%.10f,\"close\":%.10f}",
                       r.time, r.open, r.high, r.low, r.close);
}

string BuildPayload(string timeframe, MqlRates &rates[], int count)
{
   // MT5 returns series data newest-first. The bridge normalizes/sorts it server-side.
   string json = "{\"symbol\":\"" + JsonEscape(WebSymbol) + "\",\"timeframe\":\"" + timeframe + "\",\"received_at\":" + IntegerToString((long)TimeGMT()) + ",\"price\":" + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_BID), 10) + ",\"candles\":[";
   int limit = MathMin(count, HistoryBars);
   for(int i=0; i<limit; i++)
   {
      if(i > 0) json += ",";
      json += CandleJson(rates[i]);
   }
   json += "]";
   if(count > 0) json += ",\"live_candle\":" + CandleJson(rates[0]);
   json += "}";
   return json;
}

bool SendPayload(string payload)
{
   if(StringFind(BridgeUrl, "https://") != 0)
   {
      Print("Ariatrading bridge disabled: BridgeUrl must use HTTPS.");
      return false;
   }
   if(StringLen(BridgeToken) < 16 || BridgeToken == "SET_IN_MT5_TERMINAL")
   {
      Print("Ariatrading bridge disabled: configure a strong BridgeToken in EA inputs.");
      return false;
   }

   byte_array body, result;
   string headers = "Content-Type: application/json\r\nAuthorization: Bearer " + BridgeToken + "\r\n";
   StringToCharArray(payload, body, 0, WHOLE_ARRAY, CP_UTF8);
   if(ArraySize(body) > 0 && body[ArraySize(body)-1] == 0) ArrayResize(body, ArraySize(body)-1);

   string result_headers;
   ResetLastError();
   int status = WebRequest("POST", BridgeUrl, headers, HttpTimeoutMs, body, ArraySize(body), result, result_headers);
   if(status < 200 || status >= 300)
   {
      PrintFormat("Ariatrading bridge HTTP failure: status=%d error=%d", status, GetLastError());
      return false;
   }
   return true;
}

void PushTimeframe(int index)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, Tfs[index].tf, 0, HistoryBars, rates);
   if(copied <= 0)
   {
      PrintFormat("Ariatrading bridge CopyRates failed: timeframe=%s error=%d", Tfs[index].name, GetLastError());
      return;
   }
   SendPayload(BuildPayload(Tfs[index].name, rates, copied));
}

void PushAll()
{
   for(int i=0; i<ArraySize(Tfs); i++) PushTimeframe(i);
}

int OnInit()
{
   if(PollSeconds < 1) return INIT_PARAMETERS_INCORRECT;
   EventSetTimer(PollSeconds);
   Print("Ariatrading MT5 market bridge started. No order functions are present in this EA.");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   PushAll();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}
