from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv

from bot.config import BotConfig
from bot.mt5_gateway import MT5Gateway
from bot.service import BotService
from adapters.mt5_feed import MT5BarFeed
from strategy.realtime import RealtimeMonitor


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ariatrading")


def main() -> None:
    load_dotenv()
    config = BotConfig.from_env()
    service = BotService(config)
    service.set_state("RUNNING")
    feed = MT5BarFeed(terminal_path=config.mt5_terminal_path or None)
    gateway = None
    try:
        for symbol in config.symbols:
            # Realtime strategy remains the single source of signal truth.
            monitor = RealtimeMonitor(feed, symbol, config.timeframe)
            try:
                evaluation = monitor.evaluate_once()
            except Exception as exc:
                log.exception("realtime evaluation failed for %s", symbol)
                service.set_state("HALT", f"realtime evaluation failed: {symbol}: {exc}")
                service.emit("ERROR", {"symbol": symbol, "error": str(exc)}, alert=True)
                raise
            if evaluation is not None:
                signal = evaluation.signal
                service.emit("SIGNAL", {"symbol": symbol, "timeframe": config.timeframe, "bar_time": evaluation.bar_time.isoformat(), "event_id": evaluation.event_id, "action": signal.action, "reason": signal.reason, "entry_reference": signal.entry_reference, "stop_reference": signal.stop_reference, "score": None if signal.score is None else signal.score.total})
                log.info("%s %s %s", symbol, config.timeframe, signal.action)
        service.heartbeat(symbols=list(config.symbols))
        service.set_state("RUNNING")
        while True:
            time.sleep(30)
            service.heartbeat(symbols=list(config.symbols))
    finally:
        if gateway is not None:
            gateway.shutdown()
        feed.close()
        service.close()


if __name__ == "__main__":
    main()
