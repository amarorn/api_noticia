"""Detecção de surebet (arbitragem) — cobertura de todos os resultados com lucro garantido."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SurebetLeg:
    """Uma perna da arbitragem em uma casa específica."""

    outcome: str
    label: str
    bookmaker: str
    odd: float
    stake_pct: float
    stake_value: float


@dataclass
class SurebetOpportunity:
    """Oportunidade de arbitragem encontrada."""

    market_type: str
    home_team: str
    away_team: str
    legs: list[SurebetLeg]
    arbitrage_index: float
    margin_pct: float
    bankroll: float
    total_stake_value: float
    profit_value: float
    commence_time: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_type": self.market_type,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "commence_time": self.commence_time,
            "arbitrage_index": round(self.arbitrage_index, 6),
            "margin_pct": round(self.margin_pct, 4),
            "bankroll": self.bankroll,
            "total_stake_value": round(self.total_stake_value, 2),
            "profit_value": round(self.profit_value, 2),
            "warnings": self.warnings,
            "legs": [
                {
                    "outcome": leg.outcome,
                    "label": leg.label,
                    "bookmaker": leg.bookmaker,
                    "odd": round(leg.odd, 3),
                    "stake_pct": round(leg.stake_pct, 2),
                    "stake_value": round(leg.stake_value, 2),
                }
                for leg in self.legs
            ],
        }


_OUTCOME_LABELS_1X2 = {"1": "Vitória mandante", "X": "Empate", "2": "Vitória visitante"}
_OUTCOME_LABELS_2WAY = {"yes": "Sim / Over", "no": "Não / Under"}


def arbitrage_index(odds: dict[str, float]) -> float:
    """Índice de arbitragem: soma(1/odd). Lucro garantido se < 1."""
    valid = [float(o) for o in odds.values() if float(o) > 1.0]
    if len(valid) != len(odds):
        return 999.0
    return sum(1.0 / o for o in valid)


def surebet_margin_pct(index: float) -> float:
    """Margem de lucro garantido em % (0 se não há surebet)."""
    if index <= 0 or index >= 1.0:
        return 0.0
    return (1.0 / index - 1.0) * 100.0


def allocate_stakes(bankroll: float, odds: dict[str, float]) -> dict[str, float]:
    """Distribui stake por outcome para equalizar retorno em qualquer resultado."""
    index = arbitrage_index(odds)
    if index <= 0 or index >= 1.0:
        return {}
    return {outcome: bankroll * (1.0 / odd) / index for outcome, odd in odds.items()}


def _best_odds_per_outcome(
    quotes: list[dict[str, Any]],
    outcomes: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, str]]:
    """Melhor odd por resultado entre várias casas."""
    best_odds: dict[str, float] = {}
    best_sources: dict[str, str] = {}
    for quote in quotes:
        bookmaker = str(quote.get("bookmaker") or "unknown")
        odds = quote.get("odds") or {}
        for outcome in outcomes:
            raw = odds.get(outcome)
            if raw is None:
                continue
            odd = float(raw)
            if odd <= 1.0:
                continue
            if outcome not in best_odds or odd > best_odds[outcome]:
                best_odds[outcome] = odd
                best_sources[outcome] = bookmaker
    return best_odds, best_sources


def find_h2h_surebet(
    *,
    home_team: str,
    away_team: str,
    quotes: list[dict[str, Any]],
    bankroll: float = 1000.0,
    min_margin_pct: float = 0.3,
    commence_time: str | None = None,
) -> SurebetOpportunity | None:
    """Busca surebet 1X2 cruzando odds de múltiplas casas.

    ``quotes``: [{"bookmaker": "bet365", "odds": {"1": 2.1, "X": 3.4, "2": 4.0}}, ...]
    """
    outcomes = ("1", "X", "2")
    best_odds, best_sources = _best_odds_per_outcome(quotes, outcomes)
    if len(best_odds) < 3:
        return None

    index = arbitrage_index(best_odds)
    margin = surebet_margin_pct(index)
    if index >= 1.0 or margin < min_margin_pct:
        return None

    stakes = allocate_stakes(bankroll, best_odds)
    total_stake = sum(stakes.values())
    guaranteed_return = total_stake / index
    profit = guaranteed_return - total_stake

    legs: list[SurebetLeg] = []
    for outcome in outcomes:
        odd = best_odds[outcome]
        stake_val = stakes[outcome]
        label = (
            f"Vitória {home_team}" if outcome == "1"
            else f"Vitória {away_team}" if outcome == "2"
            else _OUTCOME_LABELS_1X2[outcome]
        )
        legs.append(
            SurebetLeg(
                outcome=outcome,
                label=label,
                bookmaker=best_sources[outcome],
                odd=odd,
                stake_pct=round(stake_val / bankroll * 100, 2),
                stake_value=round(stake_val, 2),
            )
        )

    warnings: list[str] = []
    unique_books = {leg.bookmaker for leg in legs}
    if len(unique_books) < 3:
        warnings.append(
            "Menos de 3 casas distintas — confirme se a mesma casa aceita apostas opostas."
        )
    warnings.append(
        "Surebets reais exigem contas em casas diferentes; odds mudam em segundos."
    )

    return SurebetOpportunity(
        market_type="h2h_3way",
        home_team=home_team,
        away_team=away_team,
        legs=legs,
        arbitrage_index=index,
        margin_pct=margin,
        bankroll=bankroll,
        total_stake_value=round(total_stake, 2),
        profit_value=round(profit, 2),
        commence_time=commence_time,
        warnings=warnings,
    )


def find_two_way_surebet(
    *,
    home_team: str,
    away_team: str,
    market_label: str,
    quotes: list[dict[str, Any]],
    bankroll: float = 1000.0,
    min_margin_pct: float = 0.3,
    commence_time: str | None = None,
) -> SurebetOpportunity | None:
    """Surebet em mercado binário (over/under, BTTS sim/não, etc.)."""
    outcomes = ("yes", "no")
    best_odds, best_sources = _best_odds_per_outcome(quotes, outcomes)
    if len(best_odds) < 2:
        return None

    index = arbitrage_index(best_odds)
    margin = surebet_margin_pct(index)
    if index >= 1.0 or margin < min_margin_pct:
        return None

    stakes = allocate_stakes(bankroll, best_odds)
    total_stake = sum(stakes.values())
    profit = bankroll - total_stake

    legs = [
        SurebetLeg(
            outcome="yes",
            label=f"{market_label} — Sim/Over",
            bookmaker=best_sources["yes"],
            odd=best_odds["yes"],
            stake_pct=round(stakes["yes"] / bankroll * 100, 2),
            stake_value=round(stakes["yes"], 2),
        ),
        SurebetLeg(
            outcome="no",
            label=f"{market_label} — Não/Under",
            bookmaker=best_sources["no"],
            odd=best_odds["no"],
            stake_pct=round(stakes["no"] / bankroll * 100, 2),
            stake_value=round(stakes["no"], 2),
        ),
    ]

    return SurebetOpportunity(
        market_type="two_way",
        home_team=home_team,
        away_team=away_team,
        legs=legs,
        arbitrage_index=index,
        margin_pct=margin,
        bankroll=bankroll,
        total_stake_value=round(total_stake, 2),
        profit_value=round(profit, 2),
        commence_time=commence_time,
        warnings=[
            "Confirme que as linhas são idênticas entre as casas (ex.: Over 2.5 vs Under 2.5).",
            "Odds mudam rápido — valide antes de apostar.",
        ],
    )


def scan_h2h_surebets(
    events: list[dict[str, Any]],
    *,
    bankroll: float = 1000.0,
    min_margin_pct: float = 0.3,
) -> list[SurebetOpportunity]:
    """Varre lista de eventos multi-casa e retorna surebets ordenados por margem."""
    found: list[SurebetOpportunity] = []
    for event in events:
        opp = find_h2h_surebet(
            home_team=str(event.get("home_team") or ""),
            away_team=str(event.get("away_team") or ""),
            quotes=list(event.get("quotes") or []),
            bankroll=bankroll,
            min_margin_pct=min_margin_pct,
            commence_time=event.get("commence_time"),
        )
        if opp:
            found.append(opp)
    found.sort(key=lambda x: x.margin_pct, reverse=True)
    return found
