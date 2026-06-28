from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

import requests

from .client import VeikkausClient
from .config import Settings
from .db import get_previous_quote, init_db, insert_quotes, upsert_draws
from .notifier import OddsChange, TelegramNotifier
from .parser import Draw, OddsQuote, flatten_odds, parse_draws
from .world_cup import filter_world_cup_draws

LOGGER = logging.getLogger(__name__)


def detect_changes(db_path: str | Path, quotes: Iterable[OddsQuote], min_abs_change: float) -> list[OddsChange]:
    changes: list[OddsChange] = []
    for quote in quotes:
        previous = get_previous_quote(db_path, quote.quote_key)
        if previous is None:
            continue
        old = float(previous["odds"])
        delta = quote.odds - old
        if abs(delta) >= min_abs_change:
            changes.append(
                OddsChange(
                    game=quote.game,
                    draw_id=quote.draw_id,
                    market=quote.market,
                    outcome=quote.outcome,
                    old_odds=old,
                    new_odds=quote.odds,
                    delta=delta,
                    fetched_at=quote.fetched_at,
                )
            )
    return changes


def scan_once(settings: Settings, games: Iterable[str] | None = None, notify: bool = True) -> dict[str, int]:
    """Fetch draws and odds once, store them and optionally send alerts."""

    init_db(settings.db_path)
    client = VeikkausClient(base_url=settings.base_url, api_key=settings.api_key)
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    selected_games = tuple(games or settings.games)

    total_draws = 0
    total_quotes = 0
    total_changes = 0
    errors = 0

    for game in selected_games:
        game = game.upper()
        try:
            draw_payload = client.get_draws(game)
            draws = parse_draws(game, draw_payload)
            if settings.world_cup_only:
                before = len(draws)
                draws = filter_world_cup_draws(draws, settings.tournament_keywords)
                LOGGER.info("%s: %s/%s open draws matched FIFA World Cup filter", game, len(draws), before)
            total_draws += upsert_draws(settings.db_path, draws)
            LOGGER.info("%s: %s selected open draws", game, len(draws))
        except requests.HTTPError as exc:
            errors += 1
            LOGGER.warning("Could not fetch draws for %s: %s", game, exc)
            continue
        except Exception:
            errors += 1
            LOGGER.exception("Unexpected draw fetch error for %s", game)
            continue

        for draw in draws:
            try:
                odds_payload = client.get_odds(game, draw.draw_id)
                quotes = flatten_odds(game, draw.draw_id, odds_payload)
                changes = detect_changes(settings.db_path, quotes, settings.min_odds_change)
                insert_quotes(settings.db_path, quotes)
                total_quotes += len(quotes)
                total_changes += len(changes)

                if notify:
                    for change in changes:
                        notifier.send(change.format_message())

            except requests.HTTPError as exc:
                # Some games/draws may not expose odds. Store draw data and continue.
                LOGGER.info("No odds available for %s draw %s: %s", game, draw.draw_id, exc)
            except Exception:
                errors += 1
                LOGGER.exception("Unexpected odds fetch error for %s draw %s", game, draw.draw_id)

    return {
        "draws": total_draws,
        "quotes": total_quotes,
        "changes": total_changes,
        "errors": errors,
    }


def run_loop(settings: Settings, games: Iterable[str] | None = None) -> None:
    """Run the monitor forever at the configured polling interval."""

    while True:
        summary = scan_once(settings, games=games, notify=True)
        LOGGER.info("Scan summary: %s", summary)
        time.sleep(settings.poll_seconds)
