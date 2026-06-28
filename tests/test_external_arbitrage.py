from veikkaus_odds_monitor.arbitrage import find_external_arbitrages
from veikkaus_odds_monitor.external_odds import parse_the_odds_api_prices


def test_parse_the_odds_api_prices_and_find_arbitrage():
    payload = [
        {
            "id": "evt1",
            "sport_key": "soccer_fifa_world_cup",
            "commence_time": "2026-06-29T17:00:00Z",
            "home_team": "Brazil",
            "away_team": "Japan",
            "bookmakers": [
                {
                    "key": "book_a",
                    "title": "Book A",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Brazil", "price": 2.2},
                                {"name": "Draw", "price": 3.8},
                                {"name": "Japan", "price": 4.0},
                            ],
                        }
                    ],
                },
                {
                    "key": "book_b",
                    "title": "Book B",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Brazil", "price": 2.0},
                                {"name": "Draw", "price": 4.3},
                                {"name": "Japan", "price": 4.6},
                            ],
                        }
                    ],
                },
            ],
        }
    ]

    prices = parse_the_odds_api_prices(payload)
    opportunities = find_external_arbitrages(prices, total_stake=1000, min_roi=0.0)

    assert len(prices) == 6
    assert len(opportunities) == 1
    assert opportunities[0].event_name == "Brazil vs Japan"
    assert opportunities[0].roi > 0
    assert {leg.bookmaker for leg in opportunities[0].legs} == {"Book A", "Book B"}
