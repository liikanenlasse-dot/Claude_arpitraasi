from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .arbitrage import ArbitrageLeg, ArbitrageOpportunity, best_prices_by_outcome
from .config import Settings
from .db import get_recent_quotes, init_db
from .external_odds import TheOddsApiClient
from .monitor import scan_once
from .normalize import canonical_team_key, normalize_text

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutrightPrice:
    event_id: str
    event_name: str
    commence_time: str | None
    sport_key: str
    market: str
    outcome: str
    odds: float
    bookmaker: str
    source: str
    event_key: str = "worldcup:winner"
    outcome_key: str | None = None


@dataclass(frozen=True)
class OutrightScanSummary:
    external_prices: int
    veikkaus_prices: int
    combined_prices: int
    outcomes: int
    opportunities: int
    errors: int
    note: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "external_prices": self.external_prices,
            "veikkaus_prices": self.veikkaus_prices,
            "combined_prices": self.combined_prices,
            "outcomes": self.outcomes,
            "opportunities": self.opportunities,
            "errors": self.errors,
            "note": self.note,
        }


def _looks_like_winner_market(market_key: str) -> bool:
    key = normalize_text(market_key)
    return key in {"outrights", "outright", "winner", "futures", "tournament winner"} or "winner" in key


def parse_the_odds_api_outright_prices(payload: Any, expected_sport_key: str = "soccer_fifa_world_cup") -> list[OutrightPrice]:
    """Flatten The Odds API outright/winner odds.

    The exact payload shape can vary by provider/market. This parser accepts the
    normal v4 sports/{sport}/odds shape: event -> bookmakers -> markets -> outcomes.
    It groups all outcomes under one canonical event: FIFA World Cup winner.
    """

    if not isinstance(payload, list):
        return []

    prices: list[OutrightPrice] = []
    for event in payload:
        if not isinstance(event, dict):
            continue
        sport_key = str(event.get("sport_key") or expected_sport_key)
        if expected_sport_key and sport_key != expected_sport_key:
            continue

        event_id = str(event.get("id") or "worldcup-outright")
        event_name = str(event.get("sport_title") or event.get("title") or "FIFA World Cup winner")
        commence_time = event.get("commence_time")

        for bookmaker in event.get("bookmakers", []) or []:
            if not isinstance(bookmaker, dict):
                continue
            bookmaker_name = str(bookmaker.get("title") or bookmaker.get("key") or "unknown")

            for market in bookmaker.get("markets", []) or []:
                if not isinstance(market, dict):
                    continue
                market_key = str(market.get("key") or "outrights")
                if not _looks_like_winner_market(market_key):
                    continue

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
                    outcome_text = str(name)
                    outcome_key = canonical_team_key(outcome_text)
                    prices.append(
                        OutrightPrice(
                            event_id=event_id,
                            event_name=event_name,
                            commence_time=str(commence_time) if commence_time else None,
                            sport_key=sport_key,
                            market=market_key,
                            outcome=outcome_text,
                            odds=odds,
                            bookmaker=bookmaker_name,
                            source="the-odds-api",
                            outcome_key=outcome_key,
                        )
                    )
    return prices


def veikkaus_rows_to_outright_prices(
    rows: Iterable[Mapping[str, Any]],
    tournament_keywords: Iterable[str],
) -> list[OutrightPrice]:
    """Best-effort conversion of Veikkaus WINNER quotes to World Cup outright prices."""

    keywords = tuple(normalize_text(item) for item in tournament_keywords)
    prices: list[OutrightPrice] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        game = str(row.get("game") or "").upper()
        title = str(row.get("title") or "")
        market = str(row.get("market") or "winner")
        outcome = str(row.get("outcome") or "")
        title_key = normalize_text(title)
        market_key = normalize_text(market)

        if game != "WINNER":
            continue
        if keywords and not any(keyword and keyword in title_key for keyword in keywords):
            continue
        if not _looks_like_winner_market(market_key) and market_key not in {"unknown", "winner"}:
            # Veikkaus payloads are not guaranteed to use market='winner', so this is permissive.
            pass
        try:
            odds = float(row.get("odds"))
        except (TypeError, ValueError):
            continue
        if odds <= 1.0 or not outcome:
            continue

        outcome_key = canonical_team_key(outcome)
        dedupe = ("veikkaus", outcome_key)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        prices.append(
            OutrightPrice(
                event_id=f"veikkaus:{game}:{row.get('draw_id')}",
                event_name=title or "Jalkapallon MM-kisat voittaja",
                commence_time=str(row.get("closes_at") or "") or None,
                sport_key="soccer_fifa_world_cup",
                market="outrights",
                outcome=outcome,
                odds=odds,
                bookmaker="Veikkaus",
                source="veikkaus",
                outcome_key=outcome_key,
            )
        )
    return prices


def calculate_outright_opportunity(
    prices: Iterable[OutrightPrice],
    *,
    total_stake: float,
    min_roi: float,
    min_outcomes: int,
) -> ArbitrageOpportunity | None:
    """Calculate tournament-winner arbitrage if enough outcomes are covered.

    This is intentionally stricter than match 1X2. A winner market can only be a
    surebet if the available outcome list covers the field. `min_outcomes` avoids
    false positives from partial feeds.
    """

    price_list = list(prices)
    best = best_prices_by_outcome(price_list)
    if len(best) < min_outcomes:
        return None

    implied_sum = sum(1.0 / price.odds for price in best.values())
    if implied_sum <= 0 or implied_sum >= 1.0:
        return None
    roi = (1.0 / implied_sum) - 1.0
    if roi < min_roi:
        return None

    guaranteed_payout = total_stake / implied_sum
    guaranteed_profit = guaranteed_payout - total_stake
    legs = tuple(
        ArbitrageLeg(
            outcome=getattr(price, "outcome", outcome),
            odds=price.odds,
            bookmaker=price.bookmaker,
            stake=total_stake * (1.0 / price.odds) / implied_sum,
            payout=guaranteed_payout,
        )
        for outcome, price in sorted(best.items())
    )

    return ArbitrageOpportunity(
        event_id="worldcup:winner",
        event_name="FIFA World Cup winner",
        commence_time=None,
        market="outrights",
        implied_sum=implied_sum,
        roi=roi,
        total_stake=total_stake,
        guaranteed_payout=guaranteed_payout,
        guaranteed_profit=guaranteed_profit,
        legs=legs,
    )


def scan_world_cup_outrights(settings: Settings) -> tuple[OutrightScanSummary, list[OutrightPrice], list[ArbitrageOpportunity]]:
    """Fetch and compare FIFA World Cup tournament-winner prices.

    This does not place bets. Veikkaus is included only if its public endpoints
    return WINNER odds that can be parsed as team outcomes.
    """

    init_db(settings.db_path)
    external_prices: list[OutrightPrice] = []
    veikkaus_prices: list[OutrightPrice] = []
    errors = 0

    if settings.the_odds_api_key:
        try:
            client = TheOddsApiClient(api_key=settings.the_odds_api_key, base_url=settings.the_odds_api_base_url)
            payload = client.get_world_cup_odds(
                sport_key=settings.the_odds_sport_key,
                regions=settings.the_odds_regions,
                markets=settings.the_odds_outright_markets,
                odds_format=settings.the_odds_odds_format,
            )
            external_prices = parse_the_odds_api_outright_prices(payload, expected_sport_key=settings.the_odds_sport_key)
        except Exception:
            LOGGER.exception("External World Cup outright fetch failed")
            errors += 1
    else:
        errors += 1

    if settings.include_veikkaus_in_arbitrage:
        try:
            scan_once(settings, games=("WINNER",), notify=False)
            recent = get_recent_quotes(settings.db_path, limit=3000)
            veikkaus_prices = veikkaus_rows_to_outright_prices(recent, settings.tournament_keywords)
        except Exception:
            LOGGER.exception("Veikkaus outright fetch failed")
            errors += 1

    combined = [*external_prices, *veikkaus_prices]
    opportunity = calculate_outright_opportunity(
        combined,
        total_stake=settings.arbitrage_total_stake,
        min_roi=settings.min_arbitrage_roi,
        min_outcomes=settings.outright_min_outcomes,
    )
    opportunities = [opportunity] if opportunity else []

    outcomes = len({price.outcome_key or price.outcome for price in combined})
    if veikkaus_prices:
        note = "Veikkauksen turnausvoittajakertoimet löytyivät ja ovat mukana vertailussa."
    elif external_prices:
        note = "Veikkaus ei palauttanut parsekelpoisia turnausvoittajakertoimia; vertailu perustuu ulkoiseen API-dataan."
    else:
        note = "Turnausvoittajakertoimia ei löytynyt. Tarkista, tukeeko API-avain/tilaus outrights-markkinaa."

    return (
        OutrightScanSummary(
            external_prices=len(external_prices),
            veikkaus_prices=len(veikkaus_prices),
            combined_prices=len(combined),
            outcomes=outcomes,
            opportunities=len(opportunities),
            errors=errors,
            note=note,
        ),
        combined,
        opportunities,
    )
