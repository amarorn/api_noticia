"""
Simulação de Monte Carlo para partidas de futebol (Copa do Mundo).

Gera distribuição de resultados amostrando de distribuições Poisson bivariadas
com correção Dixon-Coles, permitindo:
- Probabilidades 1/X/2 com incerteza amostrada
- Distribuição de placares mais prováveis
- Mercados derivados (over/under, BTTS, escanteios estimados)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from models.poisson_wc import (
    MAX_GOALS,
    dixon_coles_tau,
    expected_lambdas,
)
from pipelines.wc_stats import WcMatchFeatures


@dataclass
class MonteCarloResult:
    """Resultado de uma simulação Monte Carlo de partida."""

    prob_home: float
    prob_draw: float
    prob_away: float
    score_distribution: dict[str, float]
    expected_goals_home: float
    expected_goals_away: float
    over_2_5: float
    under_2_5: float
    both_teams_score: float
    clean_sheet_home: float
    clean_sheet_away: float
    n_simulations: int
    rho_used: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "prob_home": round(self.prob_home, 4),
            "prob_draw": round(self.prob_draw, 4),
            "prob_away": round(self.prob_away, 4),
            "expected_goals_home": round(self.expected_goals_home, 3),
            "expected_goals_away": round(self.expected_goals_away, 3),
            "over_2_5": round(self.over_2_5, 4),
            "under_2_5": round(self.under_2_5, 4),
            "both_teams_score": round(self.both_teams_score, 4),
            "clean_sheet_home": round(self.clean_sheet_home, 4),
            "clean_sheet_away": round(self.clean_sheet_away, 4),
            "top_scores": dict(list(self.score_distribution.items())[:8]),
            "n_simulations": self.n_simulations,
            "rho_used": round(self.rho_used, 4),
        }


def _sample_poisson_bivariate(
    lam_home: float,
    lam_away: float,
    rho: float,
    n: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Amostra gols de Poisson bivariado com correção Dixon-Coles via aceitação-rejeição.

    Para rho negativo (futebol típico), baixos placares são mais prováveis.
    Usamos aceitação-rejeição: amostramos Poisson independente e aceitamos
    com probabilidade proporcional a tau(i, j).
    """
    if rho == 0.0:
        return rng.poisson(lam_home, n), rng.poisson(lam_away, n)

    home_goals = np.empty(n, dtype=int)
    away_goals = np.empty(n, dtype=int)
    accepted = 0
    batch = n * 4  # amostra extra para compensar rejeições
    max_iter = 100

    for _ in range(max_iter):
        if accepted >= n:
            break
        h_batch = rng.poisson(lam_home, batch)
        a_batch = rng.poisson(lam_away, batch)

        # tau pode ser > 1 (aceitação garantida) ou < 1 (probabilística)
        # Normalizamos: tau_max = 1 + max(|rho|, |rho*lam|)
        # Simplificação: usamos min(tau, 1.0) como prob de aceitação
        for h, a in zip(h_batch, a_batch, strict=False):
            if accepted >= n:
                break
            tau = dixon_coles_tau(int(h), int(a), lam_home, lam_away, rho)
            # tau pode ser negativo para rho > 0 e placares extremos;
            # clampamos para evitar prob negativa
            accept_prob = min(max(tau, 0.0), 1.0)
            if rng.random() < accept_prob:
                home_goals[accepted] = int(h)
                away_goals[accepted] = int(a)
                accepted += 1

    # Fallback: se não conseguimos amostras suficientes, usa Poisson puro
    if accepted < n:
        home_goals[accepted:] = rng.poisson(lam_home, n - accepted)
        away_goals[accepted:] = rng.poisson(lam_away, n - accepted)

    return home_goals, away_goals


def simulate_match_mc(
    fixtures_df,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    n_simulations: int = 10_000,
    rho: float = 0.0,
    random_seed: int = 42,
) -> MonteCarloResult:
    """Simula uma partida via Monte Carlo amostrando de Poisson bivariado.

    Args:
        fixtures_df: DataFrame com histórico de jogos.
        home_team: Nome canônico do mandante.
        away_team: Nome canônico do visitante.
        features: Features pré-computadas do confronto.
        n_simulations: Número de simulações (padrão: 10.000).
        rho: Parâmetro de correlação Dixon-Coles.
        random_seed: Semente para reprodutibilidade.

    Returns:
        MonteCarloResult com probabilidades e distribuições estimadas.
    """
    rng = np.random.default_rng(random_seed)
    lam_home, lam_away = expected_lambdas(
        fixtures_df, home_team, away_team, features=features
    )

    home_goals, away_goals = _sample_poisson_bivariate(
        lam_home, lam_away, rho, n_simulations, rng
    )

    # Estatísticas agregadas
    home_wins = int(np.sum(home_goals > away_goals))
    draws = int(np.sum(home_goals == away_goals))
    away_wins = int(np.sum(home_goals < away_goals))
    total = n_simulations

    # Distribuição de placares
    scores: dict[str, int] = {}
    for h, a in zip(home_goals, away_goals, strict=False):
        key = f"{int(h)}x{int(a)}"
        scores[key] = scores.get(key, 0) + 1
    score_distribution = {
        k: round(v / total, 4)
        for k, v in sorted(scores.items(), key=lambda x: -x[1])[:15]
    }

    total_goals = home_goals + away_goals

    return MonteCarloResult(
        prob_home=home_wins / total,
        prob_draw=draws / total,
        prob_away=away_wins / total,
        score_distribution=score_distribution,
        expected_goals_home=float(np.mean(home_goals)),
        expected_goals_away=float(np.mean(away_goals)),
        over_2_5=float(np.sum(total_goals > 2.5) / total),
        under_2_5=float(np.sum(total_goals <= 2.5) / total),
        both_teams_score=float(np.sum((home_goals > 0) & (away_goals > 0)) / total),
        clean_sheet_home=float(np.sum(away_goals == 0) / total),
        clean_sheet_away=float(np.sum(home_goals == 0) / total),
        n_simulations=n_simulations,
        rho_used=rho,
    )
