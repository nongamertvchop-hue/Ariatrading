from __future__ import annotations

import json
import urllib.error
import urllib.request


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, enabled: bool = True) -> None:
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(enabled)

    def send(self, message: str) -> bool:
        if not self.enabled or not self.token or not self.chat_id:
            return False
        if not message or len(message) > 4096:
            raise ValueError("Telegram message must be 1..4096 characters")
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = json.dumps({"chat_id": self.chat_id, "text": message}).encode("utf-8")
        request = urllib.request.Request(url, body, {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return False
