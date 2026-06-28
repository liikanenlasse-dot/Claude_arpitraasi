from __future__ import annotations

import logging
from dataclasses import dataclass

from .arbitrage import ArbitrageOpportunity, find_external_arbitrages
from .config import Settings
from .db import get_recent_quotes, init_db
from .external_odds import TheOddsApiClient, parse_the_odds_api_prices
from .monitor import scan_once
from .notifier import TelegramNotifier
from .veikkaus_adapter import veikkaus_rows_to_comparable_prices

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArbitrageScanSummary:
    external_prices: int
    veikkaus_prices: int
    combined_prices: int
    opportunities: int
    errors: int

    def as_dict(self) -> dict[str, int]:
        return {
            "external_prices": self.external_prices,
            "veikkaus_prices": self.veikkaus_prices,
            "combined_prices": self.combined_prices,
            "opportunities": self.opportunities,
            "errors": self.errors,
        }


def _fetch_external_prices(settings: Settings) -> tuple[list[object], int]:
    if not settings.the_odds_api_key:
        LOGGER.warning("THE_ODDS_API_KEY is missing; external arbitrage scan skipped")
        return [], 1

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
        return parse_the_odds_api_prices(payload, expected_sport_key=settings.the_odds_sport_key), 0
    except Exception:
        LOGGER.exception("External World Cup odds fetch failed")
        return [], 1


def _fetch_veikkaus_comparable_prices(settings: Settings) -> tuple[list[object], int]:
    if not settings.include_veikkaus_in_arbitrage:
        return [], 0

    try:
        # Fetch fresh Veikkaus World Cup quotes first. This replaces the old
        # dashboard-only Veikkaus action: Veikkaus is useful here only as one
        # bookmaker inside the arbitrage comparison.
        scan_once(settings, games=settings.games, notify=False)
        rows = get_recent_quotes(settings.db_path, limit=2000)
        prices = veikkaus_rows_to_comparable_prices(
            rows,
            max_age_seconds=settings.veikkaus_quote_max_age_seconds,
        )
        return prices, 0
    except Exception:
        LOGGER.exception("Veikkaus comparable odds fetch failed")
        return [], 1


def scan_world_cup_arbitrage(settings: Settings, notify: bool = True) -> tuple[ArbitrageScanSummary, list[ArbitrageOpportunity]]:
    """Scan FIFA World Cup arbitrage across Veikkaus and external bookmaker odds.

    External odds are read through The Odds API. Veikkaus is fetched read-only and
    converted into comparable 1X2 prices when the event and outcome labels can be
    matched safely. The function never logs in and never places bets.
    """

    init_db(settings.db_path)

    external_prices, external_errors = _fetch_external_prices(settings)
    veikkaus_prices, veikkaus_errors = _fetch_veikkaus_comparable_prices(settings)
    prices = [*external_prices, *veikkaus_prices]

    opportunities = find_external_arbitrages(
        prices,
        total_stake=settings.arbitrage_total_stake,
        min_roi=settings.min_arbitrage_roi,
    )

    if notify and opportunities:
        notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
        for opportunity in opportunities:
            notifier.send(opportunity.format_message())

    return (
        ArbitrageScanSummary(
            external_prices=len(external_prices),
            veikkaus_prices=len(veikkaus_prices),
            combined_prices=len(prices),
            opportunities=len(opportunities),
            errors=external_errors + veikkaus_errors,
        ),
        opportunities,
    )
