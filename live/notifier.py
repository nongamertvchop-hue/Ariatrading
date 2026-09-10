"""Telegram and webhook alert notifications for Ariatrading Forex.

This module formats and delivers real-time trade signals, execution confirmations,
and risk rejection alerts directly to Telegram or custom webhook endpoints.
Built with standard library (urllib.request) to avoid third-party runtime dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationConfig:
    """Configuration for Telegram and webhook alerting."""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""
    enabled: bool = True

    @classmethod
    def from_env(cls) -> NotificationConfig:
        """Load notification config from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        webhook = os.getenv("WEBHOOK_ALERT_URL", "").strip()
        enabled = os.getenv("NOTIFIER_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            webhook_url=webhook,
            enabled=enabled,
        )


class Notifier:
    """Multi-channel alert dispatcher for Forex live trading."""

    def __init__(self, config: NotificationConfig | None = None) -> None:
        self.config = config or NotificationConfig.from_env()

    @property
    def is_configured(self) -> bool:
        """Check if at least one destination is configured."""
        if not self.config.enabled:
            return False
        has_tg = bool(self.config.telegram_bot_token and self.config.telegram_chat_id)
        has_webhook = bool(self.config.webhook_url)
        return has_tg or has_webhook

    def send_text(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send generic text to configured destinations."""
        if not self.is_configured:
            return False

        delivered = True
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            delivered = delivered and self._send_telegram(text, parse_mode)

        if self.config.webhook_url:
            delivered = delivered and self._send_webhook({"text": text, "timestamp": datetime.now(timezone.utc).isoformat()})

        return delivered

    def _send_telegram(self, text: str, parse_mode: str) -> bool:
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception as e:
            logger.warning("Failed to send Telegram alert: %s", e)
            return False

    def _send_webhook(self, payload: dict[str, Any]) -> bool:
        try:
            req = urllib.request.Request(
                self.config.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status in {200, 201, 204}
        except Exception as e:
            logger.warning("Failed to send Webhook alert: %s", e)
            return False

    def notify_signal(
        self,
        *,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float | None = None,
        risk_amount: float = 0.0,
        lot_size: float = 0.0,
        score: float = 0.0,
        session: str = "",
        mode: str = "DEMO",
    ) -> bool:
        """Format and broadcast confirmed Forex trading signal."""
        icon = "🟢" if direction.upper() == "BUY" or direction.upper() == "LONG" else "🔴"
        action = "BUY" if direction.upper() in {"BUY", "LONG"} else "SELL"

        msg = [
            f"<b>{icon} ARIATRADING SIGNAL DETECTED [{mode}]</b>",
            f"<b>Pair:</b> <code>{symbol.upper()}</code>",
            f"<b>Action:</b> <b>{action}</b>",
            f"<b>Entry:</b> <code>{entry:.5f}</code>",
            f"<b>Stop Loss:</b> <code>{sl:.5f}</code>",
        ]
        if tp is not None and tp > 0:
            msg.append(f"<b>Take Profit:</b> <code>{tp:.5f}</code>")

        if lot_size > 0:
            msg.append(f"<b>Suggested Lots:</b> <code>{lot_size:.2f}</code> (${risk_amount:.2f} risk)")
        if score > 0:
            msg.append(f"<b>Quality Score:</b> <code>{score:.1f}/10</code>")
        if session:
            msg.append(f"<b>Session:</b> <code>{session}</code>")

        msg.append(f"<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</i>")
        return self.send_text("\n".join(msg))

    def notify_execution(
        self,
        *,
        symbol: str,
        direction: str,
        ticket: int,
        price: float,
        volume: float,
        comment: str = "",
    ) -> bool:
        """Broadcast live order execution event."""
        action = "BUY" if direction.upper() in {"BUY", "LONG"} else "SELL"
        msg = [
            f"<b>⚡ ORDER EXECUTED #{ticket}</b>",
            f"<b>Pair:</b> <code>{symbol.upper()}</code>",
            f"<b>Action:</b> <b>{action}</b>",
            f"<b>Volume:</b> <code>{volume:.2f} lots</code>",
            f"<b>Price:</b> <code>{price:.5f}</code>",
        ]
        if comment:
            msg.append(f"<b>Comment:</b> {comment}")
        return self.send_text("\n".join(msg))

    def notify_rejection(
        self,
        *,
        symbol: str,
        direction: str,
        reason: str,
    ) -> bool:
        """Notify that a signal was caught and blocked by safety guards."""
        msg = [
            f"<b>🛡️ SIGNAL BLOCKED BY SAFETY GATE</b>",
            f"<b>Pair:</b> <code>{symbol.upper()}</code> ({direction})",
            f"<b>Reason:</b> <i>{reason}</i>",
            f"<i>Execution blocked fail-closed for safety.</i>",
        ]
        return self.send_text("\n".join(msg))

    def notify_system(self, title: str, details: str, alert_level: str = "INFO") -> bool:
        """Send system status or warning message."""
        icon = "ℹ️" if alert_level == "INFO" else ("⚠️" if alert_level == "WARN" else "🚨")
        msg = [
            f"<b>{icon} SYSTEM {alert_level}: {title}</b>",
            f"{details}",
            f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</i>",
        ]
        return self.send_text("\n".join(msg))
