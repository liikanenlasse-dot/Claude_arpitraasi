from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Protocol


class PriceLike(Protocol):
    outcome: str
    odds: float
    bookmaker: str


@dataclass(frozen=True)
class BestOutcomePrice:
    outcome: str
    odds: float
    source: str

    @property
    def bookmaker(self) -> str:
        return self.source


@dataclass(frozen=True)
class ArbitrageResult:
    implied_sum: float
    roi: float
    stakes: dict[str, float]
    guaranteed_payout: float
    guaranteed_profit: float


@dataclass(frozen=True)
class ArbitrageLeg:
    outcome: str
    odds: float
    bookmaker: str
    stake: float
    payout: float


@dataclass(frozen=True)
class ArbitrageOpportunity:
    event_id: str
    event_name: str
    commence_time: str | None
    market: str
    implied_sum: float
    roi: float
    total_stake: float
    guaranteed_payout: float
    guaranteed_profit: float
    legs: tuple[ArbitrageLeg, ...]

    def format_message(self) -> str:
        lines = [
            "⚽ FIFA World Cup arbitrage",
            f"{self.event_name}",
            f"Market: {self.market}",
            f"ROI: {self.roi * 100:.2f}%",
            f"Stake: {self.total_stake:.2f}",
            f"Guaranteed profit: {self.guaranteed_profit:.2f}",
        ]
        if self.commence_time:
            lines.insert(2, f"Kickoff: {self.commence_time}")
        lines.append("Legs:")
        for leg in self.legs:
            lines.append(f"- {leg.outcome}: {leg.stake:.2f} @ {leg.odds:.3f} ({leg.bookmaker})")
        return "\n".join(lines)


def calculate_arbitrage(prices: list[BestOutcomePrice], total_stake: float = 1000.0) -> ArbitrageResult | None:
    """Calculate a classic surebet from best prices across outcomes.

    This compatibility function is kept for older tests and simple use cases.
    A single bookmaker's prices should normally not create true arbitrage.
    """

    if len(prices) < 2:
        return None
    if total_stake <= 0:
        raise ValueError("total_stake must be positive")

    implied_sum = sum(1.0 / price.odds for price in prices if price.odds > 1.0)
    if implied_sum <= 0 or implied_sum >= 1:
        return None

    stakes = {
        price.outcome: total_stake * (1.0 / price.odds) / implied_sum
        for price in prices
    }
    guaranteed_payout = total_stake / implied_sum
    guaranteed_profit = guaranteed_payout - total_stake
    return ArbitrageResult(
        implied_sum=implied_sum,
        roi=(1.0 / implied_sum) - 1.0,
        stakes=stakes,
        guaranteed_payout=guaranteed_payout,
        guaranteed_profit=guaranteed_profit,
    )


def best_prices_by_outcome(prices: Iterable[PriceLike]) -> dict[str, PriceLike]:
    best: dict[str, PriceLike] = {}
    for price in prices:
        if price.odds <= 1.0:
            continue
        current = best.get(price.outcome)
        if current is None or price.odds > current.odds:
            best[price.outcome] = price
    return best


def calculate_opportunity(
    *,
    event_id: str,
    event_name: str,
    commence_time: str | None,
    market: str,
    prices: Iterable[PriceLike],
    total_stake: float,
    min_roi: float,
) -> ArbitrageOpportunity | None:
    if total_stake <= 0:
        raise ValueError("total_stake must be positive")

    best = best_prices_by_outcome(prices)
    if len(best) < 2:
        return None

    implied_sum = sum(1.0 / price.odds for price in best.values())
    if implied_sum <= 0 or implied_sum >= 1.0:
        return None

    roi = (1.0 / implied_sum) - 1.0
    if roi < min_roi:
        return None

    guaranteed_payout = total_stake / implied_sum
    guaranteed_profit = guaranteed_payout - total_stake
    legs = tuple(
        ArbitrageLeg(
            outcome=outcome,
            odds=price.odds,
            bookmaker=price.bookmaker,
            stake=total_stake * (1.0 / price.odds) / implied_sum,
            payout=guaranteed_payout,
        )
        for outcome, price in sorted(best.items())
    )

    return ArbitrageOpportunity(
        event_id=event_id,
        event_name=event_name,
        commence_time=commence_time,
        market=market,
        implied_sum=implied_sum,
        roi=roi,
        total_stake=total_stake,
        guaranteed_payout=guaranteed_payout,
        guaranteed_profit=guaranteed_profit,
        legs=legs,
    )


def find_external_arbitrages(
    prices: Iterable[object],
    total_stake: float = 1000.0,
    min_roi: float = 0.005,
) -> list[ArbitrageOpportunity]:
    """Find arbitrages inside a multi-bookmaker external odds feed.

    The expected price objects are produced by external_odds.parse_the_odds_api_prices
    and contain event_id, event_name, commence_time, market, outcome, odds and
    bookmaker attributes.
    """

    grouped: dict[tuple[str, str], list[object]] = defaultdict(list)
    event_meta: dict[tuple[str, str], tuple[str, str | None]] = {}

    for price in prices:
        event_id = getattr(price, "event_id")
        market = getattr(price, "market")
        key = (event_id, market)
        grouped[key].append(price)
        event_meta[key] = (getattr(price, "event_name"), getattr(price, "commence_time"))

    opportunities: list[ArbitrageOpportunity] = []
    for (event_id, market), group in grouped.items():
        event_name, commence_time = event_meta[(event_id, market)]
        opportunity = calculate_opportunity(
            event_id=event_id,
            event_name=event_name,
            commence_time=commence_time,
            market=market,
            prices=group,
            total_stake=total_stake,
            min_roi=min_roi,
        )
        if opportunity:
            opportunities.append(opportunity)

    return sorted(opportunities, key=lambda item: item.roi, reverse=True)
