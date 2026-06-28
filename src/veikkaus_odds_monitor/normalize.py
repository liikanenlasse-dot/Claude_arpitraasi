from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_TEAM_ALIASES = {
    # English / Finnish / common short forms for World Cup teams likely to appear
    "alankomaat": "netherlands",
    "argentiina": "argentina",
    "australia": "australia",
    "belgia": "belgium",
    "belgium": "belgium",
    "brasilia": "brazil",
    "brazil": "brazil",
    "canada": "canada",
    "kanada": "canada",
    "colombia": "colombia",
    "kolumbia": "colombia",
    "croatia": "croatia",
    "kroatia": "croatia",
    "denmark": "denmark",
    "tanska": "denmark",
    "dr congo": "dr congo",
    "kongon demokraattinen tasavalta": "dr congo",
    "ecuador": "ecuador",
    "england": "england",
    "englanti": "england",
    "espanja": "spain",
    "finland": "finland",
    "suomi": "finland",
    "france": "france",
    "ranska": "france",
    "germany": "germany",
    "saksa": "germany",
    "ghana": "ghana",
    "ivory coast": "ivory coast",
    "cote d ivoire": "ivory coast",
    "norsunluurannikko": "ivory coast",
    "japan": "japan",
    "japani": "japan",
    "mexico": "mexico",
    "meksiko": "mexico",
    "morocco": "morocco",
    "marokko": "morocco",
    "netherlands": "netherlands",
    "norway": "norway",
    "norja": "norway",
    "paraguay": "paraguay",
    "portugal": "portugal",
    "portugali": "portugal",
    "senegal": "senegal",
    "south africa": "south africa",
    "etela afrikka": "south africa",
    "spain": "spain",
    "sweden": "sweden",
    "ruotsi": "sweden",
    "switzerland": "switzerland",
    "sveitsi": "switzerland",
    "united states": "united states",
    "usa": "united states",
    "yhdysvallat": "united states",
    "uruguay": "uruguay",
}

_DRAW_ALIASES = {"x", "draw", "tie", "tasapeli", "tasuri"}
_HOME_ALIASES = {"1", "home", "kotivoitto"}
_AWAY_ALIASES = {"2", "away", "vierasvoitto"}


@dataclass(frozen=True)
class EventTeams:
    home: str
    away: str
    home_key: str
    away_key: str

    @property
    def event_key(self) -> str:
        return event_key_from_team_keys(self.home_key, self.away_key)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_team_key(value: str | None) -> str:
    normalized = normalize_text(value)
    return _TEAM_ALIASES.get(normalized, normalized)


def event_key_from_team_keys(team_a_key: str, team_b_key: str) -> str:
    first, second = sorted([team_a_key, team_b_key])
    return f"match:{first}|{second}"


def event_key_from_teams(team_a: str | None, team_b: str | None) -> str | None:
    a = canonical_team_key(team_a)
    b = canonical_team_key(team_b)
    if not a or not b or a == b:
        return None
    return event_key_from_team_keys(a, b)


def parse_event_teams(title: str | None) -> EventTeams | None:
    """Parse home/away teams from common match-title formats."""

    if not title:
        return None
    text = str(title).strip()
    separators = [" vs ", " v ", " - ", " – ", " — ", " / "]
    for sep in separators:
        if sep in text:
            home, away = [part.strip() for part in text.split(sep, 1)]
            home_key = canonical_team_key(home)
            away_key = canonical_team_key(away)
            if home and away and home_key and away_key and home_key != away_key:
                return EventTeams(home=home, away=away, home_key=home_key, away_key=away_key)
    return None


def outcome_role(outcome: str | None, teams: EventTeams | None = None) -> str | None:
    key = normalize_text(outcome)
    if not key:
        return None
    if key in _DRAW_ALIASES:
        return "draw"
    if key in _HOME_ALIASES:
        return "home"
    if key in _AWAY_ALIASES:
        return "away"
    if teams:
        team_key = canonical_team_key(outcome)
        if team_key == teams.home_key:
            return "home"
        if team_key == teams.away_key:
            return "away"
    return None


def display_outcome_for_role(role: str, teams: EventTeams | None, fallback: str) -> str:
    if role == "draw":
        return "Draw"
    if role == "home" and teams:
        return teams.home
    if role == "away" and teams:
        return teams.away
    return fallback
