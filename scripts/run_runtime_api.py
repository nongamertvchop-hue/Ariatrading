from __future__ import annotations

from dotenv import load_dotenv
import uvicorn

from bot.config import BotConfig
from bot.health_api import create_app
from bot.service import BotService


load_dotenv()
config = BotConfig.from_env()
service = BotService(config)
service.set_state("RUNNING")
app = create_app(
    health_provider=lambda: service.heartbeat(),
    event_provider=lambda: service.store.recent_events(100),
    allowed_ips=config.allowed_ips,
)


if __name__ == "__main__":
    uvicorn.run(app, host=config.health_host, port=config.health_port, log_level="info")
