from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv

from adapters.mt5_feed import MT5BarFeed
from bot.config import BotConfig
from bot.service import BotService
from strategy.realtime import RealtimeMonitor


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ariatrading")


def main() -> None:
    load_dotenv()
    config = BotConfig.from_env()
    poll_seconds = max(1.0, float(os.getenv("BOT_POLL_SECONDS", "2")))
    service = BotService(config)
    feed = MT5BarFeed(terminal_path=config.mt5_terminal_path or None)
    monitors = {symbol: RealtimeMonitor(feed, symbol, config.timeframe) for symbol in config.symbols}
    service.set_state("RUNNING")
    try:
        while True:
            cycle_failed = False
            for symbol, monitor in monitors.items():
                try:
                    service.authorize_provider_call()
                    evaluation = monitor.evaluate_once()
                    if evaluation is not None:
                        signal = evaluation.signal
                        payload = {
                            "symbol": symbol,
                            "timeframe": config.timeframe,
                            "bar_time": evaluation.bar_time.isoformat(),
                            "event_id": evaluation.event_id,
                            "action": signal.action,
                            "reason": signal.reason,
                            "entry_reference": signal.entry_reference,
                            "stop_reference": signal.stop_reference,
                            "score": None if signal.score is None else signal.score.total,
                        }
                        service.emit("SIGNAL", payload)
                        log.info("%s %s %s", symbol, config.timeframe, signal.action)
                except Exception as exc:
                    cycle_failed = True
                    log.exception("realtime evaluation failed for %s", symbol)
                    service.emit("ERROR", {"symbol": symbol, "error": str(exc)}, alert=True)
            service.heartbeat(symbols=list(config.symbols), cycle_failed=cycle_failed)
            service.set_state("DEGRADED", "one or more provider/strategy evaluations failed" if cycle_failed else "")
            if not cycle_failed:
                service.set_state("RUNNING")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        service.set_state("STOPPED", "operator interrupt")
    except Exception as exc:
        service.set_state("HALT", str(exc))
        service.emit("FATAL", {"error": str(exc)}, alert=True)
        raise
    finally:
        feed.close()
        service.close()


if __name__ == "__main__":
    main()
