from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE = {"1", "true", "yes", "on"}


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in _TRUE


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class BotConfig:
    mode: str = "paper"
    symbols: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY")
    timeframe: str = "15m"
    sqlite_path: str = "data/ariatrading.db"
    redis_url: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    notifier_enabled: bool = True
    health_host: str = "127.0.0.1"
    health_port: int = 8080
    allowed_ips: tuple[str, ...] = ()
    max_request_rate: float = 5.0
    max_burst: int = 10
    mt5_terminal_path: str = ""
    mt5_login: int | None = None
    mt5_password: str = ""
    mt5_server: str = ""
    magic_number: int = 8808
    default_risk_per_trade: float = 0.01
    allow_live: bool = False

    @classmethod
    def from_env(cls) -> "BotConfig":
        login = os.getenv("MT5_LOGIN", "").strip()
        mode = os.getenv("BOT_MODE", "paper").strip().lower()
        config = cls(
            mode=mode,
            symbols=_csv("DEFAULT_SYMBOLS", "EURUSD,GBPUSD,USDJPY"),
            timeframe=os.getenv("DEFAULT_TIMEFRAME", "15m").strip(),
            sqlite_path=os.getenv("SQLITE_PATH", "data/ariatrading.db").strip(),
            redis_url=os.getenv("REDIS_URL", "").strip(),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            notifier_enabled=_bool("NOTIFIER_ENABLED", True),
            health_host=os.getenv("HEALTH_HOST", "127.0.0.1").strip(),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
            allowed_ips=_csv("HEALTH_ALLOWED_IPS", ""),
            max_request_rate=float(os.getenv("MAX_REQUEST_RATE", "5")),
            max_burst=int(os.getenv("MAX_REQUEST_BURST", "10")),
            mt5_terminal_path=os.getenv("MT5_TERMINAL_PATH", "").strip(),
            mt5_login=int(login) if login else None,
            mt5_password=os.getenv("MT5_PASSWORD", ""),
            mt5_server=os.getenv("MT5_SERVER", "").strip(),
            magic_number=int(os.getenv("MT5_MAGIC_NUMBER", "8808")),
            default_risk_per_trade=float(os.getenv("DEFAULT_RISK_PER_TRADE", "0.01")),
            allow_live=_bool("ALLOW_LIVE", False),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.mode not in {"paper", "demo", "live"}:
            raise ValueError("BOT_MODE must be paper, demo, or live")
        if self.mode == "live" and not self.allow_live:
            raise RuntimeError("LIVE mode is fail-closed: set ALLOW_LIVE=1 only in a separately reviewed deployment")
        if not self.symbols:
            raise ValueError("DEFAULT_SYMBOLS must not be empty")
        if self.max_request_rate <= 0 or self.max_burst < 1:
            raise ValueError("rate-limit settings must be positive")
        if not 0 < self.default_risk_per_trade <= 1:
            raise ValueError("DEFAULT_RISK_PER_TRADE must be in (0,1]")
        if self.mode in {"demo", "live"} and self.mt5_login is not None and not self.mt5_server:
            raise ValueError("MT5_SERVER is required when an authenticated MT5 account is configured")
