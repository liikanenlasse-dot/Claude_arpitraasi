from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from .normalize import EventTeams, canonical_team_key, event_key_from_teams, outcome_role

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExternalOutcomePrice:
    event_id: str
    event_name: str
    commence_time: str | None
    sport_key: str
    market: str
    outcome: str
    odds: float
    bookmaker: str
    source: str = "the-odds-api"
    event_key: str | None = None
    outcome_key: str | None = None


class TheOddsApiClient:
    """Read-only client for The Odds API v4.

    It fetches odds from a licensed odds aggregator. It does not log in to any
    bookmaker and it does not place bets.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.the-odds-api.com", timeout: int = 20) -> None:
        if not api_key:
            raise ValueError("THE_ODDS_API_KEY is required for external bookmaker odds")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "veikkaus-odds-monitor/0.3 read-only"})

    def get_world_cup_odds(
        self,
        sport_key: str = "soccer_fifa_world_cup",
        regions: str = "eu,uk",
        markets: str = "h2h",
        odds_format: str = "decimal",
    ) -> Any:
        url = f"{self.base_url}/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        LOGGER.debug("GET %s params=%s", url, {**params, "apiKey": "***"})
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


def parse_the_odds_api_prices(payload: Any, expected_sport_key: str = "soccer_fifa_world_cup") -> list[ExternalOutcomePrice]:
    """Flatten The Odds API event payload into comparable outcome prices."""

    if not isinstance(payload, list):
        return []

    prices: list[ExternalOutcomePrice] = []
    for event in payload:
        if not isinstance(event, dict):
            continue

        sport_key = str(event.get("sport_key") or expected_sport_key)
        if expected_sport_key and sport_key != expected_sport_key:
            continue

        event_id = str(event.get("id") or "")
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        event_name = f"{home} vs {away}".strip(" vs") or event_id
        commence_time = event.get("commence_time")
        event_key = event_key_from_teams(home, away)
        teams = None
        if event_key:
            teams = EventTeams(
                home=home,
                away=away,
                home_key=canonical_team_key(home),
                away_key=canonical_team_key(away),
            )

        for bookmaker in event.get("bookmakers", []) or []:
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_name = str(bookmaker.get("title") or bookmaker.get("key") or "unknown")

            for market in bookmaker.get("markets", []) or []:
                if not isinstance(market, dict):
                    continue
                market_key = str(market.get("key") or "unknown")

                for outcome in market.get("outcomes", []) or []:
                    if not isinstance(outcome, dict):
                        continue
                    name = outcome.get("name")
                    price = outcome.get("price")
                    try:
                        odds = float(price)
                    except (TypeError, ValueError):
                        continue
                    if odds <= 1.0 or not name:
                        continue
                    role = outcome_role(str(name), teams) if market_key == "h2h" else None
                    prices.append(
                        ExternalOutcomePrice(
                            event_id=event_id,
                            event_name=event_name,
                            commence_time=str(commence_time) if commence_time else None,
                            sport_key=sport_key,
                            market=market_key,
                            outcome=str(name),
                            odds=odds,
                            bookmaker=bookmaker_name,
                            event_key=event_key,
                            outcome_key=role,
                        )
                    )
    return prices
