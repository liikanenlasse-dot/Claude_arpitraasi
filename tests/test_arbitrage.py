from veikkaus_odds_monitor.arbitrage import BestOutcomePrice, calculate_arbitrage


def test_arbitrage_detected_and_stakes_sum_to_total():
    result = calculate_arbitrage(
        [
            BestOutcomePrice("A", 2.10, "book1"),
            BestOutcomePrice("B", 2.05, "book2"),
        ],
        total_stake=1000,
    )

    assert result is not None
    assert result.implied_sum < 1
    assert result.guaranteed_profit > 0
    assert round(sum(result.stakes.values()), 2) == 1000.00


def test_no_arbitrage_returns_none():
    result = calculate_arbitrage(
        [
            BestOutcomePrice("A", 1.80, "book1"),
            BestOutcomePrice("B", 1.90, "book2"),
        ],
        total_stake=1000,
    )
    assert result is None
