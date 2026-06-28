from __future__ import annotations

import logging
from dataclasses import dataclass

from .arbitrage import ArbitrageOpportunity, find_external_arbitrages
from .config import Settings
from .external_odds import TheOddsApiClient, parse_the_odds_api_prices
from .notifier import TelegramNotifier

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArbitrageScanSummary:
    external_prices: int
    opportunities: int
    errors: int

    def as_dict(self) -> dict[str, int]:
        return {
            "external_prices": self.external_prices,
            "opportunities": self.opportunities,
            "errors": self.errors,
        }


def scan_world_cup_arbitrage(settings: Settings, notify: bool = True) -> tuple[ArbitrageScanSummary, list[ArbitrageOpportunity]]:
    """Scan FIFA World Cup arbitrage using external multi-bookmaker odds.

    The first supported external provider is The Odds API with sport key
    soccer_fifa_world_cup. This gives one safe API-based way to compare multiple
    bookmakers without scraping bookmaker websites.
    """

    errors = 0
    if not settings.the_odds_api_key:
        LOGGER.warning("THE_ODDS_API_KEY is missing; external arbitrage scan skipped")
        return ArbitrageScanSummary(external_prices=0, opportunities=0, errors=1), []

    try:
        client = TheOddsApiClient(
            api_key=settings.the_odds_api_key,
            base_url=settings.the_odds_api_base_url,
        )
        payload = client.get_world_cup_odds(
            sport_key=settings.the_odds_sport_key,
            regions=settings.the_odds_regions,
            markets=settings.the_odds_markets,
            odds_format=settings.the_odds_odds_format,
        )
        prices = parse_the_odds_api_prices(payload, expected_sport_key=settings.the_odds_sport_key)
        opportunities = find_external_arbitrages(
            prices,
            total_stake=settings.arbitrage_total_stake,
            min_roi=settings.min_arbitrage_roi,
        )
    except Exception:
        LOGGER.exception("World Cup arbitrage scan failed")
        return ArbitrageScanSummary(external_prices=0, opportunities=0, errors=1), []

    if notify and opportunities:
        notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        for opportunity in opportunities:
            notifier.send(opportunity.format_message())

    return ArbitrageScanSummary(external_prices=len(prices), opportunities=len(opportunities), errors=errors), opportunities
