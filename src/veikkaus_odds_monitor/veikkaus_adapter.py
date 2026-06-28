from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Any

from .normalize import display_outcome_for_role, outcome_role, parse_event_teams


@dataclass(frozen=True)
class VeikkausComparablePrice:
    event_id: str
    event_name: str
    commence_time: str | None
    sport_key: str
    market: str
    outcome: str
    odds: float
    bookmaker: str = "Veikkaus"
    source: str = "veikkaus"
    event_key: str | None = None
    outcome_key: str | None = None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_value(row: Mapping[str, Any], key: str) -> Any:
    try:
        return row[key]
    except Exception:
        return None


def veikkaus_rows_to_comparable_prices(
    rows: Iterable[Mapping[str, Any]],
    *,
    max_age_seconds: int = 600,
) -> list[VeikkausComparablePrice]:
    """Convert latest Veikkaus quote rows into h2h-comparable prices.

    Veikkaus often labels 1X2 outcomes as 1, X and 2. For arbitrage we map
    those to canonical home/draw/away roles so they can be compared with The
    Odds API bookmaker odds for the same FIFA World Cup fixture.
    """

    now = datetime.now(timezone.utc)
    seen: set[tuple[str, str, str]] = set()
    prices: list[VeikkausComparablePrice] = []

    for row in rows:
        title = str(_row_value(row, "title") or "")
        teams = parse_event_teams(title)
        if not teams:
            continue

        fetched_at_raw = _row_value(row, "fetched_at")
        fetched_at = _parse_iso(str(fetched_at_raw) if fetched_at_raw else None)
        if fetched_at is not None and fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if fetched_at is not None and (now - fetched_at).total_seconds() > max_age_seconds:
            continue

        raw_outcome = str(_row_value(row, "outcome") or "")
        role = outcome_role(raw_outcome, teams)
        if role is None:
            continue

        try:
            odds = float(_row_value(row, "odds"))
        except (TypeError, ValueError):
            continue
        if odds <= 1.0:
            continue

        event_key = teams.event_key
        dedupe_key = (event_key, "h2h", role)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        prices.append(
            VeikkausComparablePrice(
                event_id=f"veikkaus:{_row_value(row, 'game')}:{_row_value(row, 'draw_id')}",
                event_name=f"{teams.home} vs {teams.away}",
                commence_time=str(_row_value(row, "closes_at") or "") or None,
                sport_key="soccer_fifa_world_cup",
                market="h2h",
                outcome=display_outcome_for_role(role, teams, raw_outcome),
                odds=odds,
                event_key=event_key,
                outcome_key=role,
            )
        )

    return prices
