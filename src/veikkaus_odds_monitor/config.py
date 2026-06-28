from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    base_url: str = "https://www.veikkaus.fi"
    api_key: str = "ROBOT"
    games: tuple[str, ...] = ("SCORE", "WINNER", "SPORT", "MULTISCORE")
    poll_seconds: int = 120
    db_path: Path = Path("data/veikkaus_odds.sqlite3")
    min_odds_change: float = 0.05
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # World Cup / arbitrage settings. External odds are read through a legal API
    # provider. Do not add code that logs in, scrapes HTML or places bets.
    world_cup_only: bool = True
    tournament_keywords: tuple[str, ...] = (
        "fifa world cup",
        "world cup",
        "fifa mm",
        "mm-kisat",
        "mm kisat",
        "jalkapallon mm",
    )
    the_odds_api_key: str | None = None
    the_odds_api_base_url: str = "https://api.the-odds-api.com"
    the_odds_sport_key: str = "soccer_fifa_world_cup"
    the_odds_regions: str = "eu,uk"
    the_odds_markets: str = "h2h"
    the_odds_odds_format: str = "decimal"
    min_arbitrage_roi: float = 0.005
    arbitrage_total_stake: float = 1000.0


def _parse_games(value: str | None) -> tuple[str, ...]:
    if not value:
        return ("SCORE", "WINNER", "SPORT", "MULTISCORE")
    games = tuple(item.strip().upper() for item in value.split(",") if item.strip())
    return games or ("SCORE", "WINNER", "SPORT", "MULTISCORE")


def _parse_keywords(value: str | None) -> tuple[str, ...]:
    if not value:
        return (
            "fifa world cup",
            "world cup",
            "fifa mm",
            "mm-kisat",
            "mm kisat",
            "jalkapallon mm",
        )
    keywords = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    return keywords or ("fifa world cup", "world cup")


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def load_settings(env_file: str | os.PathLike[str] | None = ".env") -> Settings:
    """Load settings from .env and process environment.

    Environment variables override defaults. The .env file is optional.
    """

    if env_file:
        load_dotenv(env_file, override=False)

    return Settings(
        base_url=os.getenv("VEIKKAUS_BASE_URL", "https://www.veikkaus.fi").rstrip("/"),
        api_key=os.getenv("VEIKKAUS_API_KEY", "ROBOT"),
        games=_parse_games(os.getenv("VEIKKAUS_GAMES")),
        poll_seconds=_get_int("VEIKKAUS_POLL_SECONDS", 120),
        db_path=Path(os.getenv("VEIKKAUS_DB_PATH", "data/veikkaus_odds.sqlite3")),
        min_odds_change=_get_float("VEIKKAUS_MIN_ODDS_CHANGE", 0.05),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        world_cup_only=_get_bool("WORLD_CUP_ONLY", True),
        tournament_keywords=_parse_keywords(os.getenv("TOURNAMENT_KEYWORDS")),
        the_odds_api_key=os.getenv("THE_ODDS_API_KEY") or None,
        the_odds_api_base_url=os.getenv("THE_ODDS_API_BASE_URL", "https://api.the-odds-api.com").rstrip("/"),
        the_odds_sport_key=os.getenv("THE_ODDS_SPORT_KEY", "soccer_fifa_world_cup"),
        the_odds_regions=os.getenv("THE_ODDS_REGIONS", "eu,uk"),
        the_odds_markets=os.getenv("THE_ODDS_MARKETS", "h2h"),
        the_odds_odds_format=os.getenv("THE_ODDS_ODDS_FORMAT", "decimal"),
        min_arbitrage_roi=_get_float("MIN_ARBITRAGE_ROI", 0.005),
        arbitrage_total_stake=_get_float("ARBITRAGE_TOTAL_STAKE", 1000.0),
    )


def normalize_games(games: Iterable[str] | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not games:
        return default
    return tuple(game.strip().upper() for game in games if game.strip()) or default
