"""Hawkes process para modelagem de timing de gols em futebol.

Modelo de intensidade auto-excitante: após cada gol, a probabilidade de
outro gol sobe temporariamente (clustering de gols por pressão/retaliação).

Intensidade:
    λ(t) = μ(t) + Σ_{t_i < t} α × exp(-β × (t - t_i))

Onde:
- μ(t): baseline (pode vir do NHPP da Fase 1)
- α: salto da intensidade após cada gol (α_self para gol próprio, α_cross para adversário)
- β: taxa de decaimento (~0.1 → meia-vida ~7min)

Sampling via thinning algorithm (Lewis & Shedler 1979).

Spec: docs/specs/spec-fase-3-modelo-avancado.md § 5.1
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class HawkesParameters:
    """Parâmetros do processo Hawkes para gols de futebol."""

    alpha_self: float = 0.08     # boost após gol do próprio time
    alpha_cross: float = 0.12    # boost após gol do adversário (retaliação)
    beta: float = 0.25           # taxa de decaimento (meia-vida ≈ ln2/β ≈ 2.8 min)

    @property
    def half_life(self) -> float:
        """Meia-vida do excitação em minutos."""
        if self.beta <= 0:
            return float("inf")
        return np.log(2) / self.beta

    @property
    def is_stable(self) -> bool:
        """Processo é estável se (α_self + α_cross) / β < 1."""
        return (self.alpha_self + self.alpha_cross) / max(self.beta, 1e-9) < 1.0


@dataclass
class HawkesGoalEvent:
    """Um gol observado no processo Hawkes."""

    minute: float
    team: str  # "home" ou "away"


@dataclass
class HawkesSimulationResult:
    """Resultado de uma simulação Hawkes do restante do jogo."""

    simulated_goals_home: list[float] = field(default_factory=list)
    simulated_goals_away: list[float] = field(default_factory=list)
    n_goals_home: int = 0
    n_goals_away: int = 0


def hawkes_intensity(
    t: float,
    past_goals: list[HawkesGoalEvent],
    params: HawkesParameters,
    mu_base: float,
    team: str = "home",
) -> float:
    """Calcula a intensidade λ(t) do processo Hawkes para um time.

    Args:
        t: minuto atual.
        past_goals: gols já marcados (ambos os times).
        params: parâmetros (α_self, α_cross, β).
        mu_base: intensidade baseline (do modelo NHPP/Poisson).
        team: "home" ou "away" — para distinguir self/cross.

    Returns:
        λ(t) — intensidade instantânea.
    """
    excitation = 0.0
    for goal in past_goals:
        if goal.minute >= t:
            continue
        dt = t - goal.minute
        if goal.team == team:
            excitation += params.alpha_self * np.exp(-params.beta * dt)
        else:
            excitation += params.alpha_cross * np.exp(-params.beta * dt)

    return mu_base + excitation


def simulate_hawkes_remaining(
    t_now: float,
    t_end: float,
    mu_home: float,
    mu_away: float,
    params: HawkesParameters,
    past_goals: list[HawkesGoalEvent],
    rng: np.random.Generator | None = None,
) -> HawkesSimulationResult:
    """Simula gols restantes usando processo Hawkes (thinning algorithm).

    Usa o algoritmo de Lewis & Shedler para sampling de processos
    com intensidade variável: propõe eventos com taxa λ_max e aceita
    com probabilidade λ(t)/λ_max.

    Args:
        t_now: minuto atual (início da simulação).
        t_end: fim do jogo (90 ou 120).
        mu_home: baseline de intensidade home (gols/minuto).
        mu_away: baseline de intensidade away.
        params: parâmetros Hawkes.
        past_goals: gols já observados.
        rng: gerador de números aleatórios.

    Returns:
        HawkesSimulationResult com gols simulados.
    """
    if rng is None:
        rng = np.random.default_rng()

    # Copiar goals para não modificar a lista original
    all_goals = list(past_goals)
    simulated_home: list[float] = []
    simulated_away: list[float] = []

    t = t_now

    # λ_max upper bound: baseline + todos os decaimentos possíveis
    # No pior caso, logo após um gol: μ + (n_goals_passados + n_futuros) × α
    # Usamos bound conservador que recalculamos periodicamente
    max_total_goals = 10  # bound prático

    while t < t_end:
        # Upper bound para intensidade total (home + away)
        lambda_home = hawkes_intensity(t, all_goals, params, mu_home, "home")
        lambda_away = hawkes_intensity(t, all_goals, params, mu_away, "away")
        lambda_max = (lambda_home + lambda_away) * 1.5 + 0.01  # margem de segurança

        if lambda_max <= 0:
            break

        # Próximo evento proposto (exponencial com taxa λ_max)
        dt = rng.exponential(1.0 / lambda_max)
        t += dt

        if t >= t_end:
            break

        # Aceitar/rejeitar (thinning)
        lambda_home_t = hawkes_intensity(t, all_goals, params, mu_home, "home")
        lambda_away_t = hawkes_intensity(t, all_goals, params, mu_away, "away")
        lambda_total_t = lambda_home_t + lambda_away_t

        u = rng.uniform()
        if u <= lambda_total_t / lambda_max:
            # Aceitar: decidir qual time marcou
            if rng.uniform() < lambda_home_t / max(lambda_total_t, 1e-9):
                simulated_home.append(t)
                all_goals.append(HawkesGoalEvent(minute=t, team="home"))
            else:
                simulated_away.append(t)
                all_goals.append(HawkesGoalEvent(minute=t, team="away"))

            # Safety: não simular mais que max_total_goals
            if len(simulated_home) + len(simulated_away) >= max_total_goals:
                break

    return HawkesSimulationResult(
        simulated_goals_home=simulated_home,
        simulated_goals_away=simulated_away,
        n_goals_home=len(simulated_home),
        n_goals_away=len(simulated_away),
    )


def simulate_hawkes_batch(
    t_now: float,
    t_end: float,
    mu_home: float,
    mu_away: float,
    params: HawkesParameters,
    past_goals: list[HawkesGoalEvent],
    n_simulations: int = 5000,
    seed: int | None = None,
) -> dict[str, NDArray[np.float64]]:
    """Executa N simulações Hawkes e retorna distribuição de gols.

    Returns:
        Dict com:
        - "goals_home": array (N,) de gols home simulados
        - "goals_away": array (N,) de gols away simulados
        - "prob_home_win": P(home vence considerando score atual)
        - "prob_draw": P(empate)
        - "prob_away_win": P(away vence)
    """
    rng = np.random.default_rng(seed)
    goals_home = np.zeros(n_simulations)
    goals_away = np.zeros(n_simulations)

    for i in range(n_simulations):
        result = simulate_hawkes_remaining(
            t_now, t_end, mu_home, mu_away, params, past_goals, rng
        )
        goals_home[i] = result.n_goals_home
        goals_away[i] = result.n_goals_away

    return {
        "goals_home": goals_home,
        "goals_away": goals_away,
        "mean_goals_home": float(goals_home.mean()),
        "mean_goals_away": float(goals_away.mean()),
    }


def hawkes_probs_from_simulation(
    sim_result: dict[str, NDArray[np.float64]],
    current_home_score: int,
    current_away_score: int,
) -> dict[str, float]:
    """Converte resultado de simulação Hawkes em probabilidades 1X2.

    Soma gols simulados ao placar atual para determinar resultado final.
    """
    goals_h = sim_result["goals_home"]
    goals_a = sim_result["goals_away"]
    n = len(goals_h)

    final_h = current_home_score + goals_h
    final_a = current_away_score + goals_a

    prob_home = float((final_h > final_a).sum() / n)
    prob_draw = float((final_h == final_a).sum() / n)
    prob_away = float((final_h < final_a).sum() / n)

    return {"1": prob_home, "X": prob_draw, "2": prob_away}
