from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from .parser import Draw

DRAW_ALIASES = {"draw", "tie", "x", "tasapeli", "tasuri", "riste"}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = strip_accents(str(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact_text(value: str | None) -> str:
    return normalize_text(value).replace(" ", "")


def is_draw_outcome(name: str | None) -> bool:
    return normalize_text(name) in DRAW_ALIASES


def outcome_matches_team(outcome: str, team: str, threshold: float = 0.72) -> bool:
    out = compact_text(outcome)
    tm = compact_text(team)
    if not out or not tm:
        return False
    if out == tm or out in tm or tm in out:
        return True
    return SequenceMatcher(None, out, tm).ratio() >= threshold


def raw_blob(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def draw_is_world_cup(draw: Draw, keywords: tuple[str, ...]) -> bool:
    """Best-effort filter for Veikkaus draws.

    Veikkaus sport-game payloads vary by game type. We inspect the visible title
    and preserved raw JSON blob. If no tournament field exists, the filter will
    only accept rows whose text explicitly mentions World Cup / MM-kisat.
    """

    haystack = normalize_text(" ".join([draw.title or "", raw_blob(draw.raw)]))
    return any(normalize_text(keyword) in haystack for keyword in keywords)


def filter_world_cup_draws(draws: list[Draw], keywords: tuple[str, ...]) -> list[Draw]:
    return [draw for draw in draws if draw_is_world_cup(draw, keywords)]


def infer_teams_from_title(title: str | None) -> tuple[str | None, str | None]:
    if not title:
        return None, None
    # Common football title forms: "Brazil - Japan", "Brazil v Japan", "Brazil vs Japan".
    pieces = re.split(r"\s+(?:vs?\.?|v\.?|against)\s+|\s+[-–—]\s+", title, maxsplit=1, flags=re.I)
    if len(pieces) != 2:
        return None, None
    home = pieces[0].strip()
    away = pieces[1].strip()
    return (home or None), (away or None)
