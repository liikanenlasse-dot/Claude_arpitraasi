from veikkaus_odds_monitor.outrights import parse_the_odds_api_outright_prices, calculate_outright_opportunity


def test_parse_outright_prices():
    payload = [
        {
            "id": "wc",
            "sport_key": "soccer_fifa_world_cup",
            "sport_title": "FIFA World Cup",
            "bookmakers": [
                {"title": "Book A", "markets": [{"key": "outrights", "outcomes": [{"name": "Brazil", "price": 6.0}]}]}
            ],
        }
    ]
    prices = parse_the_odds_api_outright_prices(payload)
    assert len(prices) == 1
    assert prices[0].outcome == "Brazil"
    assert prices[0].outcome_key == "brazil"


def test_outright_requires_minimum_outcomes():
    payload = [
        {
            "id": "wc",
            "sport_key": "soccer_fifa_world_cup",
            "bookmakers": [
                {"title": "Book A", "markets": [{"key": "outrights", "outcomes": [{"name": "Brazil", "price": 6.0}, {"name": "France", "price": 6.0}]}]}
            ],
        }
    ]
    prices = parse_the_odds_api_outright_prices(payload)
    assert calculate_outright_opportunity(prices, total_stake=1000, min_roi=0.001, min_outcomes=3) is None
