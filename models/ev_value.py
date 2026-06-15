from dataclasses import dataclass

from config import settings
from models.economics import coase_effective_min_edge


@dataclass
class OutcomeValue:
    outcome: str
    model_prob: float
    odd: float
    implied_prob: float
    fair_odd: float
    expected_value: float
    kelly_full: float
    kelly_quarter: float


@dataclass
class MatchValueReport:
    home_team: str
    away_team: str
    outcomes: list[OutcomeValue]
    best: OutcomeValue | None


def _kelly_fraction(prob: float, odd: float) -> float:
    if odd <= 1.0:
        return 0.0
    numerator = (prob * odd) - 1.0
    denominator = odd - 1.0
    if denominator <= 0:
        return 0.0
    return max(0.0, numerator / denominator)


def _sanitize_prob(prob: float) -> float:
    return max(0.0, min(1.0, prob))


def evaluate_outcome(outcome: str, prob: float, odd: float, *, house_prob: float | None = None) -> OutcomeValue:
    """Avalia EV de uma aposta.

    Se `house_prob` for fornecido (probabilidade real da casa, ex: generosity_prob
    sem margem), usa ela no lugar de `1/odd` para calcular a prob implícita.
    EV = P_modelo / P_casa * (1 - margem_casa) — quando `house_prob` está presente,
    a margem já foi removida, então EV = (P_modelo * odd_cru) - 1 ainda funciona
    corretamente, mas o `implied_prob` fica mais preciso para referência e o
    filtro de "odd suspeita" ganha uma baseline real.
    """
    p = _sanitize_prob(prob)
    if house_prob is not None and house_prob > 0:
        implied = _sanitize_prob(house_prob)
    else:
        implied = 1.0 / odd if odd > 0 else 1.0
    fair_odd = (1.0 / p) if p > 0 else 999.0
    ev = (p * odd) - 1.0 if odd > 0 else -1.0
    kelly = _kelly_fraction(p, odd)
    return OutcomeValue(
        outcome=outcome,
        model_prob=p,
        odd=odd,
        implied_prob=implied,
        fair_odd=fair_odd,
        expected_value=ev,
        kelly_full=kelly,
        kelly_quarter=kelly * 0.25,
    )


def evaluate_match(
    home_team: str,
    away_team: str,
    probabilities: dict[str, float],
    odds: dict[str, float],
    min_edge: float | None = None,
) -> MatchValueReport:
    threshold = coase_effective_min_edge(min_edge or settings.ev_min_edge)
    outcomes: list[OutcomeValue] = []
    for key in ("1", "X", "2"):
        odd = float(odds.get(key, 0.0))
        prob = float(probabilities.get(key, 0.0))
        if odd <= 1.0:
            continue
        outcomes.append(evaluate_outcome(key, prob, odd))

    outcomes.sort(key=lambda item: item.expected_value, reverse=True)
    best = outcomes[0] if outcomes and outcomes[0].expected_value >= threshold else None
    return MatchValueReport(
        home_team=home_team,
        away_team=away_team,
        outcomes=outcomes,
        best=best,
    )
