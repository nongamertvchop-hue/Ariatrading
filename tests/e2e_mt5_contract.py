from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from live import mt5_market_bridge as bridge


class FakeMT5:
    TIMEFRAME_M1 = "M1"
    TIMEFRAME_M5 = "M5"
    TIMEFRAME_M15 = "M15"
    TIMEFRAME_M30 = "M30"
    TIMEFRAME_H1 = "H1"
    TIMEFRAME_H4 = "H4"
    TIMEFRAME_D1 = "D1"

    def __init__(self) -> None:
        current = int(time.time())
        base = (current // 900 - 20) * 900
        self.completed = [
            SimpleNamespace(
                time=base + index * 900,
                open=1.1000 + index * 0.0001,
                high=1.1005 + index * 0.0001,
                low=1.0995 + index * 0.0001,
                close=1.1002 + index * 0.0001,
            )
            for index in range(20)
        ]
        self.live = [
            SimpleNamespace(time=base + 20 * 900, open=1.1020, high=1.1028, low=1.1018, close=1.1024)
        ]
        self.tick = SimpleNamespace(time=base + 20 * 900 + 30, bid=1.1023, ask=1.1025)

    def symbol_select(self, symbol: str, enabled: bool) -> bool:
        return symbol == "EURUSD" and enabled is True

    def copy_rates_from_pos(self, symbol: str, _timeframe: object, start_pos: int, count: int):
        assert symbol == "EURUSD"
        if start_pos == 1:
            return self.completed[:count]
        if start_pos == 0:
            return self.live[:count]
        raise AssertionError(start_pos)

    def symbol_info_tick(self, symbol: str):
        assert symbol == "EURUSD"
        return self.tick

    def last_error(self) -> str:
        return "fake MT5 error"


def main() -> None:
    fake = FakeMT5()
    bridge.mt5 = fake
    bridge.TIMEFRAME_MAP.update(
        {
            "1m": fake.TIMEFRAME_M1,
            "5m": fake.TIMEFRAME_M5,
            "15m": fake.TIMEFRAME_M15,
            "30m": fake.TIMEFRAME_M30,
            "1h": fake.TIMEFRAME_H1,
            "4h": fake.TIMEFRAME_H4,
            "1D": fake.TIMEFRAME_D1,
        }
    )
    payload = bridge.market_payload("EURUSD", "15m", 20)
    assert payload["source"] == "mt5"
    assert payload["execution"] == "NONE"
    assert len(payload["candles"]) == 20
    assert payload["live_candle"]["time"] > payload["candles"][-1]["time"]
    assert payload["tick"]["bid"] <= payload["price"] <= payload["tick"]["ask"]

    target = Path(".github/e2e_mt5_payload.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
