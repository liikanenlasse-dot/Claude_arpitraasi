from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator


@dataclass(frozen=True)
class Draw:
    game: str
    draw_id: str
    list_index: str | None
    title: str | None
    closes_at: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class OddsQuote:
    game: str
    draw_id: str
    market: str
    outcome: str
    odds: float
    source_path: str
    fetched_at: str
    raw: dict[str, Any]

    @property
    def quote_key(self) -> str:
        text = "|".join([self.game, self.draw_id, self.market, self.outcome])
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _title_from_row(row: dict[str, Any]) -> str | None:
    candidates = [
        row.get("name"),
        row.get("title"),
        row.get("eventName"),
        row.get("description"),
    ]

    competitors = row.get("competitors")
    if isinstance(competitors, list):
        names = [str(item.get("name")) for item in competitors if isinstance(item, dict) and item.get("name")]
        if names:
            candidates.append(" - ".join(names))

    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


def parse_draws(game: str, payload: Any) -> list[Draw]:
    """Parse draws from Veikkaus draw-list payload.

    The official payload can vary by game. This parser deliberately accepts a
    few likely container keys and preserves the full raw draw for later review.
    """

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = (
            payload.get("draws")
            or payload.get("items")
            or payload.get("results")
            or payload.get("data")
            or []
        )
    else:
        rows = []

    draws: list[Draw] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        draw_id = row.get("id") or row.get("drawId") or row.get("drawNumber")
        if draw_id is None:
            continue

        closes_at = (
            row.get("closeTime")
            or row.get("closingTime")
            or row.get("closeTimeUTC")
            or row.get("gameStartTime")
            or row.get("startTime")
        )

        draws.append(
            Draw(
                game=game.upper(),
                draw_id=str(draw_id),
                list_index=_stringify(row.get("listIndex")),
                title=_title_from_row(row),
                closes_at=_stringify(closes_at),
                raw=row,
            )
        )
    return draws


def _walk(value: Any, path: str = "$", parent: dict[str, Any] | None = None) -> Iterator[tuple[str, Any, dict[str, Any] | None]]:
    yield path, value, parent
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}", value)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]", parent)


def _extract_outcome_name(node: dict[str, Any], parent: dict[str, Any] | None, fallback: str) -> str:
    keys = ("name", "outcome", "outcomeName", "competitorName", "selectionName", "label", "description")
    for key in keys:
        value = node.get(key)
        if isinstance(value, (str, int, float)):
            return str(value)

    if parent:
        for key in keys:
            value = parent.get(key)
            if isinstance(value, (str, int, float)):
                return str(value)
    return fallback


def _extract_market_name(path: str, node: dict[str, Any], parent: dict[str, Any] | None) -> str:
    keys = ("market", "marketName", "betType", "type", "gameName")
    for key in keys:
        value = node.get(key)
        if isinstance(value, (str, int, float)):
            return str(value)
    if parent:
        for key in keys:
            value = parent.get(key)
            if isinstance(value, (str, int, float)):
                return str(value)
    # Last useful path segment as market fallback.
    return path.rsplit(".", 1)[0].replace("$.", "") or "unknown"


def flatten_odds(game: str, draw_id: str, payload: Any, fetched_at: str | None = None) -> list[OddsQuote]:
    """Extract decimal odds from a Veikkaus odds payload.

    Veikkaus game-specific payloads are not uniform. This function searches for
    dict nodes that include a numeric 'odds', 'price' or 'winShare' field and
    converts those nodes into OddsQuote rows. Unknown fields are preserved in raw.
    """

    fetched_at = fetched_at or utc_now_iso()
    quotes: list[OddsQuote] = []
    seen: set[tuple[str, str, str, float]] = set()

    odds_keys = ("odds", "price", "winShare", "coefficient")
    for path, value, parent in _walk(payload):
        if not isinstance(value, dict):
            continue

        odds_value = None
        for key in odds_keys:
            candidate = value.get(key)
            if isinstance(candidate, (int, float)) and float(candidate) > 1:
                odds_value = float(candidate)
                break
            if isinstance(candidate, str):
                try:
                    parsed = float(candidate.replace(",", "."))
                    if parsed > 1:
                        odds_value = parsed
                        break
                except ValueError:
                    pass

        if odds_value is None:
            continue

        fallback = path.replace("$.", "")
        market = _extract_market_name(path, value, parent)
        outcome = _extract_outcome_name(value, parent, fallback)
        identity = (str(market), str(outcome), path, odds_value)
        if identity in seen:
            continue
        seen.add(identity)

        quotes.append(
            OddsQuote(
                game=game.upper(),
                draw_id=str(draw_id),
                market=str(market),
                outcome=str(outcome),
                odds=odds_value,
                source_path=path,
                fetched_at=fetched_at,
                raw=value,
            )
        )

    return quotes


def raw_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
