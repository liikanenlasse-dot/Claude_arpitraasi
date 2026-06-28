from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Any

import requests

from .client import VeikkausClient
from .config import Settings
from .db import get_recent_quotes, init_db
from .monitor import scan_once
from .parser import Draw, flatten_odds, parse_draws
from .veikkaus_adapter import veikkaus_rows_to_comparable_prices
from .world_cup import filter_world_cup_draws

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class VeikkausGameDiagnostic:
    game: str
    raw_draws: int = 0
    world_cup_draws: int = 0
    quotes_from_selected_draws: int = 0
    errors: int = 0
    sample_raw_titles: tuple[str, ...] = ()
    sample_world_cup_titles: tuple[str, ...] = ()
    sample_quote_outcomes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VeikkausDiagnosticSummary:
    games_checked: int
    raw_draws: int
    world_cup_draws: int
    fetched_quotes: int
    recent_db_quotes: int
    comparable_prices: int
    errors: int
    games: tuple[VeikkausGameDiagnostic, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, int]:
        return {
            "games_checked": self.games_checked,
            "raw_draws": self.raw_draws,
            "world_cup_draws": self.world_cup_draws,
            "fetched_quotes": self.fetched_quotes,
            "recent_db_quotes": self.recent_db_quotes,
            "comparable_prices": self.comparable_prices,
            "errors": self.errors,
        }


def _title(draw: Draw) -> str:
    return draw.title or f"{draw.game} draw {draw.draw_id}"


def _sample(values: Iterable[str], n: int = 8) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in out:
            out.append(value)
        if len(out) >= n:
            break
    return tuple(out)


def diagnose_veikkaus_pipeline(settings: Settings, games: Iterable[str] | None = None, *, max_odds_draws_per_game: int = 10) -> VeikkausDiagnosticSummary:
    """Inspect why Veikkaus odds may or may not enter the arbitrage comparison.

    This is read-only. It checks the same Veikkaus games as the normal monitor,
    counts raw draws, counts World Cup-filtered draws, attempts to fetch odds for
    a small sample of selected draws, then runs the normal scan once so the DB
    reflects the latest available comparable rows.
    """

    init_db(settings.db_path)
    client = VeikkausClient(base_url=settings.base_url, api_key=settings.api_key)

    game_rows: list[VeikkausGameDiagnostic] = []
    total_raw = 0
    total_wc = 0
    total_fetched_quotes = 0
    errors = 0

    selected_games = tuple(games or settings.games)

    for game in selected_games:
        game = game.upper()
        raw_draws: list[Draw] = []
        selected_draws: list[Draw] = []
        quote_count = 0
        game_errors = 0
        quote_samples: list[str] = []

        try:
            payload = client.get_draws(game)
            raw_draws = parse_draws(game, payload)
            selected_draws = filter_world_cup_draws(raw_draws, settings.tournament_keywords) if settings.world_cup_only else raw_draws
        except requests.HTTPError as exc:
            LOGGER.warning("Veikkaus diagnostics could not fetch draws for %s: %s", game, exc)
            game_errors += 1
        except Exception:
            LOGGER.exception("Veikkaus diagnostics unexpected draw fetch error for %s", game)
            game_errors += 1

        for draw in selected_draws[:max_odds_draws_per_game]:
            try:
                odds_payload = client.get_odds(game, draw.draw_id)
                quotes = flatten_odds(game, draw.draw_id, odds_payload)
                quote_count += len(quotes)
                for q in quotes[:5]:
                    quote_samples.append(f"{_title(draw)} | {q.market} | {q.outcome} @ {q.odds}")
            except requests.HTTPError:
                # Some Veikkaus games/draws do not expose a separate odds endpoint.
                pass
            except Exception:
                LOGGER.exception("Veikkaus diagnostics odds fetch error for %s draw %s", game, draw.draw_id)
                game_errors += 1

        total_raw += len(raw_draws)
        total_wc += len(selected_draws)
        total_fetched_quotes += quote_count
        errors += game_errors
        game_rows.append(
            VeikkausGameDiagnostic(
                game=game,
                raw_draws=len(raw_draws),
                world_cup_draws=len(selected_draws),
                quotes_from_selected_draws=quote_count,
                errors=game_errors,
                sample_raw_titles=_sample(_title(d) for d in raw_draws),
                sample_world_cup_titles=_sample(_title(d) for d in selected_draws),
                sample_quote_outcomes=_sample(quote_samples),
            )
        )

    # Run the normal pipeline once; this is what the arbitrage scanner uses.
    try:
        scan_once(settings, games=settings.games, notify=False)
    except Exception:
        LOGGER.exception("Veikkaus diagnostics normal scan_once failed")
        errors += 1

    recent = get_recent_quotes(settings.db_path, limit=2000)
    comparable = veikkaus_rows_to_comparable_prices(recent, max_age_seconds=settings.veikkaus_quote_max_age_seconds)

    notes: list[str] = []
    if total_raw == 0:
        notes.append("Veikkauksen rajapinta ei palauttanut yhtään avointa kohdetta valituille pelityypeille.")
    elif total_wc == 0:
        notes.append("Veikkaus palautti kohteita, mutta mikään ei läpäissyt World Cup -suodatusta. Lisää TOURNAMENT_KEYWORDS-arvoihin Veikkauksen käyttämä sarja-/turnausteksti tai tarkista raakakohteiden nimet.")
    elif total_fetched_quotes == 0:
        notes.append("World Cup -kohteita löytyi, mutta niille ei saatu kertoimia nykyisistä odds-endpointeista.")
    elif len(comparable) == 0:
        notes.append("Kertoimia löytyi, mutta niitä ei pystytty muuntamaan turvallisesti 1/X/2-muotoon. Usein syy on, että ottelun nimi tai tulosvaihtoehdot eivät ole muodossa Team A - Team B / 1 / X / 2.")
    else:
        notes.append("Veikkaus-kertoimia löytyi ja ne voidaan ottaa arbitraasivertailuun.")

    return VeikkausDiagnosticSummary(
        games_checked=len(selected_games),
        raw_draws=total_raw,
        world_cup_draws=total_wc,
        fetched_quotes=total_fetched_quotes,
        recent_db_quotes=len(recent),
        comparable_prices=len(comparable),
        errors=errors,
        games=tuple(game_rows),
        notes=tuple(notes),
    )
