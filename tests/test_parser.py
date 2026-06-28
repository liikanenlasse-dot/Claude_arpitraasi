from veikkaus_odds_monitor.parser import flatten_odds, parse_draws


def test_parse_draws_from_draws_key():
    payload = {
        "draws": [
            {
                "id": 123,
                "listIndex": 4,
                "competitors": [{"name": "Team A"}, {"name": "Team B"}],
                "closeTime": "2026-06-28T18:00:00Z",
            }
        ]
    }

    draws = parse_draws("SCORE", payload)

    assert len(draws) == 1
    assert draws[0].game == "SCORE"
    assert draws[0].draw_id == "123"
    assert draws[0].title == "Team A - Team B"


def test_flatten_odds_finds_nested_prices():
    payload = {
        "markets": [
            {
                "marketName": "winner",
                "outcomes": [
                    {"name": "Team A", "odds": 2.15},
                    {"name": "Team B", "odds": "1.85"},
                ],
            }
        ]
    }

    quotes = flatten_odds("WINNER", "123", payload, fetched_at="2026-06-28T12:00:00Z")

    assert len(quotes) == 2
    assert {quote.outcome for quote in quotes} == {"Team A", "Team B"}
    assert {quote.odds for quote in quotes} == {2.15, 1.85}
