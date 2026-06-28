from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OddsChange:
    game: str
    draw_id: str
    market: str
    outcome: str
    old_odds: float
    new_odds: float
    delta: float
    fetched_at: str

    def format_message(self) -> str:
        direction = "nousi" if self.delta > 0 else "laski"
        return (
            "Veikkaus-kerroin muuttui\n"
            f"Peli: {self.game}\n"
            f"Kohde: {self.draw_id}\n"
            f"Markkina: {self.market}\n"
            f"Valinta: {self.outcome}\n"
            f"Kerroin {direction}: {self.old_odds:.2f} → {self.new_odds:.2f} "
            f"({self.delta:+.2f})\n"
            f"Aika: {self.fetched_at}"
        )


class TelegramNotifier:
    def __init__(self, bot_token: str | None, chat_id: str | None, timeout: int = 15) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, text: str) -> bool:
        if not self.enabled:
            LOGGER.info("Telegram not configured. Message would be: %s", text)
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(url, json={"chat_id": self.chat_id, "text": text}, timeout=self.timeout)
        response.raise_for_status()
        return True
