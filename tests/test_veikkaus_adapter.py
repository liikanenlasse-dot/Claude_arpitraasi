from veikkaus_odds_monitor.arbitrage import find_external_arbitrages
from veikkaus_odds_monitor.external_odds import parse_the_odds_api_prices
from veikkaus_odds_monitor.veikkaus_adapter import veikkaus_rows_to_comparable_prices


def test_veikkaus_1x2_rows_can_join_external_h2h_prices():
    veikkaus_rows = [
        {
            "title": "Brazil - Japan",
            "fetched_at": "2099-01-01T00:00:00+00:00",
            "game": "SPORT",
            "draw_id": "123",
            "outcome": "1",
            "odds": 2.6,
            "closes_at": "2026-06-29T17:00:00Z",
        },
        {
            "title": "Brazil - Japan",
            "fetched_at": "2099-01-01T00:00:00+00:00",
            "game": "SPORT",
            "draw_id": "123",
            "outcome": "X",
            "odds": 3.8,
            "closes_at": "2026-06-29T17:00:00Z",
        },
        {
            "title": "Brazil - Japan",
            "fetched_at": "2099-01-01T00:00:00+00:00",
            "game": "SPORT",
            "draw_id": "123",
            "outcome": "2",
            "odds": 4.0,
            "closes_at": "2026-06-29T17:00:00Z",
        },
    ]
    external_payload = [
        {
            "id": "evt1",
            "sport_key": "soccer_fifa_world_cup",
            "commence_time": "2026-06-29T17:00:00Z",
            "home_team": "Brazil",
            "away_team": "Japan",
            "bookmakers": [
                {
                    "key": "book_b",
                    "title": "Book B",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Brazil", "price": 2.0},
                                {"name": "Draw", "price": 4.4},
                                {"name": "Japan", "price": 4.8},
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    prices = [*parse_the_odds_api_prices(external_payload), *veikkaus_rows_to_comparable_prices(veikkaus_rows)]
    opportunities = find_external_arbitrages(prices, total_stake=1000, min_roi=0.0)

    assert len(opportunities) == 1
    assert {leg.bookmaker for leg in opportunities[0].legs} == {"Veikkaus", "Book B"}
