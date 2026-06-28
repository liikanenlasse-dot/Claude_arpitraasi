from __future__ import annotations

import argparse
import logging
from typing import Sequence

from .arb_monitor import scan_world_cup_arbitrage
from .config import load_settings, normalize_games
from .monitor import run_loop, scan_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Veikkaus + World Cup odds monitor")
    parser.add_argument(
        "command",
        choices=("scan", "loop", "arbitrage", "arb"),
        help="scan = fetch Veikkaus once, loop = keep polling, arbitrage/arb = scan FIFA World Cup surebets from external API",
    )
    parser.add_argument(
        "--games",
        help="Comma-separated Veikkaus game list, e.g. SCORE,WINNER,SPORT",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file. Use empty value to skip .env loading.",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Do not send Telegram notifications during this run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    env_file = args.env_file if args.env_file else None
    settings = load_settings(env_file=env_file)
    games = normalize_games(args.games.split(",") if args.games else None, settings.games)

    if args.command == "scan":
        summary = scan_once(settings, games=games, notify=not args.no_notify)
        print(summary)
        return 0

    if args.command == "loop":
        run_loop(settings, games=games)
        return 0

    if args.command in {"arbitrage", "arb"}:
        summary, opportunities = scan_world_cup_arbitrage(settings, notify=not args.no_notify)
        print(summary.as_dict())
        for opportunity in opportunities:
            print("-" * 80)
            print(opportunity.format_message())
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
