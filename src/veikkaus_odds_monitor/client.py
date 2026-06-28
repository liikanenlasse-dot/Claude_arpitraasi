from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class VeikkausClient:
    """Small read-only client for Veikkaus public sport-game endpoints.

    This client intentionally implements only GET requests. It does not log in,
    submit tickets, check wagers or send any betting-related POST requests.
    """

    def __init__(self, base_url: str = "https://www.veikkaus.fi", api_key: str = "ROBOT", timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-ESA-API-Key": api_key,
                "User-Agent": "veikkaus-odds-monitor/0.1 read-only",
            }
        )

    def get_json(self, path: str, **params: Any) -> Any:
        url = f"{self.base_url}{path}"
        LOGGER.debug("GET %s params=%s", url, params)
        response = self.session.get(url, params={k: v for k, v in params.items() if v is not None}, timeout=self.timeout)
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    def get_draws(self, game: str) -> Any:
        """Return open draws for a Veikkaus sport game.

        Common games: SCORE, WINNER, SPORT, MULTISCORE, PICKTWO, PICKTHREE,
        PERFECTA, TRIFECTA.
        """
        return self.get_json(f"/api/sport-open-games/v1/games/{game.upper()}/draws")

    def get_odds(self, game: str, draw_id: int | str) -> Any:
        """Return odds for a specific draw when the game exposes an odds endpoint."""
        return self.get_json(f"/api/sport-odds/v1/games/{game.upper()}/draws/{draw_id}/odds")
