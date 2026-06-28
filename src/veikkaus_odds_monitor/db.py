from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .parser import Draw, OddsQuote, raw_json

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS draws (
    game TEXT NOT NULL,
    draw_id TEXT NOT NULL,
    list_index TEXT,
    title TEXT,
    closes_at TEXT,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game, draw_id)
);

CREATE TABLE IF NOT EXISTS odds_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_key TEXT NOT NULL,
    game TEXT NOT NULL,
    draw_id TEXT NOT NULL,
    market TEXT NOT NULL,
    outcome TEXT NOT NULL,
    odds REAL NOT NULL,
    source_path TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_odds_quote_key_time ON odds_quotes (quote_key, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_odds_game_draw ON odds_quotes (game, draw_id);
CREATE INDEX IF NOT EXISTS idx_odds_fetched_at ON odds_quotes (fetched_at DESC);

CREATE VIEW IF NOT EXISTS latest_odds AS
SELECT oq.*
FROM odds_quotes oq
JOIN (
    SELECT quote_key, MAX(fetched_at) AS max_fetched_at
    FROM odds_quotes
    GROUP BY quote_key
) latest
ON latest.quote_key = oq.quote_key AND latest.max_fetched_at = oq.fetched_at;
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_draws(db_path: str | Path, draws: Iterable[Draw]) -> int:
    rows = list(draws)
    if not rows:
        return 0
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO draws (game, draw_id, list_index, title, closes_at, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(game, draw_id) DO UPDATE SET
                list_index = excluded.list_index,
                title = excluded.title,
                closes_at = excluded.closes_at,
                raw_json = excluded.raw_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (draw.game, draw.draw_id, draw.list_index, draw.title, draw.closes_at, raw_json(draw.raw))
                for draw in rows
            ],
        )
        conn.commit()
    return len(rows)


def insert_quotes(db_path: str | Path, quotes: Iterable[OddsQuote]) -> int:
    rows = list(quotes)
    if not rows:
        return 0
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO odds_quotes
                (quote_key, game, draw_id, market, outcome, odds, source_path, fetched_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    quote.quote_key,
                    quote.game,
                    quote.draw_id,
                    quote.market,
                    quote.outcome,
                    quote.odds,
                    quote.source_path,
                    quote.fetched_at,
                    raw_json(quote.raw),
                )
                for quote in rows
            ],
        )
        conn.commit()
    return len(rows)


def get_previous_quote(db_path: str | Path, quote_key: str) -> sqlite3.Row | None:
    with connect(db_path) as conn:
        return conn.execute(
            """
            SELECT *
            FROM odds_quotes
            WHERE quote_key = ?
            ORDER BY fetched_at DESC, id DESC
            LIMIT 1
            """,
            (quote_key,),
        ).fetchone()


def get_recent_quotes(db_path: str | Path, limit: int = 200) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT oq.*, d.title, d.closes_at
                FROM odds_quotes oq
                LEFT JOIN draws d ON d.game = oq.game AND d.draw_id = oq.draw_id
                ORDER BY oq.fetched_at DESC, oq.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )


def get_draws(db_path: str | Path, limit: int = 200) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT *
                FROM draws
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )
