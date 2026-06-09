"""MLE para calibração dos parâmetros α e β do processo Hawkes.

Estima os parâmetros de auto-excitação via máxima verossimilhança sobre
sequências de gols reconstruídas do dataset de fixtures históricas.

Log-likelihood do Hawkes com kernel exponencial:
    ℓ = Σᵢ log(λ(tᵢ)) - ∫₀ᵀ λ(s) ds

A integral tem solução analítica para kernel exp(-β × Δt):
    ∫₀ᵀ λ(s) ds = μ×T + Σᵢ (α/β) × (1 - exp(-β × (T - tᵢ)))

Spec: docs/specs/spec-fase-3-modelo-avancado.md § 5.1
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from config import settings
from models.wc_hawkes import HawkesGoalEvent, HawkesParameters
from pipelines.wc_intensity_profile import default_intensity_profile


@dataclass
class HawkesFitResult:
    """Resultado da calibração MLE do Hawkes."""

    alpha_self: float
    alpha_cross: float
    beta: float
    n_matches: int
    n_goals: int
    log_likelihood: float
    converged: bool
    half_life_minutes: float

    @property
    def is_stable(self) -> bool:
        """Processo é estável se branching ratio < 1."""
        return (self.alpha_self + self.alpha_cross) / max(self.beta, 1e-9) < 1.0

    def to_parameters(self) -> HawkesParameters:
        """Converte para HawkesParameters usável pelo simulador."""
        return HawkesParameters(
            alpha_self=self.alpha_self,
            alpha_cross=self.alpha_cross,
            beta=self.beta,
        )


def _nhpp_cumulative_fraction(minute: float, match_minutes: int = 90) -> float:
    """Fração cumulativa de gols esperados até o minuto dado."""
    profile = default_intensity_profile()
    total_weighted = sum(b.weight * b.duration for b in profile)
    cumul = 0.0
    for b in profile:
        start = b.start_min
        end = min(b.end_min, minute)
        if start < end:
            cumul += b.weight * (end - start)
    return cumul / total_weighted


def _reconstruct_goal_times(
    home_score: int,
    away_score: int,
    match_minutes: int = 90,
    rng: np.random.Generator | None = None,
) -> list[HawkesGoalEvent]:
    """Reconstrói minutos de gol usando amostragem inversa do perfil NHPP.

    Para cada gol, amostramos um minuto respeitando a distribuição temporal
    do perfil de intensidade (mais gols no final do que no início).
    """
    if rng is None:
        rng = np.random.default_rng()

    total_goals = home_score + away_score
    if total_goals == 0:
        return []

    # Gerar tempos amostrando da CDF NHPP via inversão
    profile = default_intensity_profile()
    # Construir CDF discreta minuto a minuto
    minutes = np.arange(1, match_minutes + 1, dtype=float)
    weights = np.zeros(match_minutes)
    for b in profile:
        for m_idx in range(match_minutes):
            m = m_idx + 1
            if b.start_min < m <= b.end_min:
                weights[m_idx] = b.weight

    # Normalizar para probabilidade
    weights /= weights.sum()

    # Amostrar minutos para todos os gols
    goal_minutes = rng.choice(minutes, size=total_goals, replace=True, p=weights)
    goal_minutes.sort()

    # Atribuir home/away: primeiros home_score são home, restante away
    # (ordem aleatória dentro de cada time)
    teams = ["home"] * home_score + ["away"] * away_score
    rng.shuffle(teams)

    # Re-sort por minuto mas manter a atribuição de times embaralhada
    events = []
    for i, minute in enumerate(goal_minutes):
        events.append(HawkesGoalEvent(minute=float(minute), team=teams[i]))

    return events


def build_goal_sequences(
    min_season: int = 2010,
    max_season: int = 2026,
    seed: int = 42,
) -> list[tuple[list[HawkesGoalEvent], float, float, int]]:
    """Constrói sequências de gols por jogo para calibração.

    Returns:
        Lista de tuplas (goal_events, mu_home, mu_away, match_minutes)
        onde mu é a taxa baseline por minuto estimada.
    """
    from ingest.fixtures.world_cup import load_wc_fixtures

    fixtures = load_wc_fixtures(include_fifa=True)
    if fixtures.empty:
        return []

    df = fixtures[
        (fixtures["season"] >= min_season)
        & (fixtures["season"] <= max_season)
        & fixtures["home_score"].notna()
        & fixtures["away_score"].notna()
    ].copy()

    if df.empty:
        return []

    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    rng = np.random.default_rng(seed)
    match_minutes = 90

    # Taxa média global (baseline para normalização)
    mean_home = df["home_score"].mean() / match_minutes
    mean_away = df["away_score"].mean() / match_minutes

    sequences = []
    for _, game in df.iterrows():
        hs = int(game["home_score"])
        as_ = int(game["away_score"])
        match_seed = rng.integers(0, 2**31)
        match_rng = np.random.default_rng(match_seed)

        events = _reconstruct_goal_times(hs, as_, match_minutes, match_rng)
        # μ proporcional à força do time (ajustado pelo gol total da partida)
        mu_h = max(mean_home, 0.005)
        mu_a = max(mean_away, 0.005)

        sequences.append((events, mu_h, mu_a, match_minutes))

    return sequences


def hawkes_log_likelihood(
    params_vec: np.ndarray,
    sequences: list[tuple[list[HawkesGoalEvent], float, float, int]],
) -> float:
    """Log-likelihood negativa do Hawkes (para minimização).

    params_vec: [alpha_self, alpha_cross, beta]
    """
    alpha_self = params_vec[0]
    alpha_cross = params_vec[1]
    beta = params_vec[2]

    # Restrições de domínio
    if alpha_self < 0 or alpha_cross < 0 or beta <= 0:
        return 1e10

    # Estabilidade: branching ratio < 1
    if (alpha_self + alpha_cross) / beta >= 0.99:
        return 1e10

    total_ll = 0.0

    for events, mu_home, mu_away, T in sequences:
        if not events:
            # Sem gols: contribuição = -∫₀ᵀ λ(s) ds = -(μ_h + μ_a) × T
            total_ll += -(mu_home + mu_away) * T
            continue

        # Separar eventos por time
        for team, mu_base in [("home", mu_home), ("away", mu_away)]:
            team_events = [e for e in events if e.team == team]
            all_events = events

            # Soma dos log(λ(tᵢ)) para eventos deste time
            for ev in team_events:
                # Intensidade no momento do gol
                excitation = 0.0
                for prev in all_events:
                    if prev.minute >= ev.minute:
                        continue
                    dt = ev.minute - prev.minute
                    if prev.team == team:
                        excitation += alpha_self * np.exp(-beta * dt)
                    else:
                        excitation += alpha_cross * np.exp(-beta * dt)

                lam = mu_base + excitation
                if lam <= 0:
                    return 1e10
                total_ll += np.log(lam)

            # Integral compensadora: ∫₀ᵀ λ(s) ds
            # = μ × T + Σᵢ (α/β)(1 - exp(-β(T - tᵢ)))
            integral = mu_base * T
            for ev_all in all_events:
                dt_end = T - ev_all.minute
                if dt_end <= 0:
                    continue
                if ev_all.team == team:
                    integral += (alpha_self / beta) * (1 - np.exp(-beta * dt_end))
                else:
                    integral += (alpha_cross / beta) * (1 - np.exp(-beta * dt_end))

            total_ll -= integral

    return -total_ll  # Negativo para minimização


def fit_hawkes_mle(
    sequences: list[tuple[list[HawkesGoalEvent], float, float, int]] | None = None,
    min_season: int = 2010,
    max_season: int = 2026,
    seed: int = 42,
) -> HawkesFitResult:
    """Calibra parâmetros Hawkes via MLE (L-BFGS-B).

    Args:
        sequences: sequências pré-construídas (opcional).
        min_season: filtro mínimo de edição WC.
        max_season: filtro máximo.
        seed: seed para reprodutibilidade.

    Returns:
        HawkesFitResult com parâmetros calibrados.
    """
    if sequences is None:
        sequences = build_goal_sequences(min_season, max_season, seed)

    n_matches = len(sequences)
    n_goals = sum(len(evts) for evts, _, _, _ in sequences)

    if n_matches == 0:
        # Retorna defaults se não há dados
        return HawkesFitResult(
            alpha_self=0.08,
            alpha_cross=0.12,
            beta=0.25,
            n_matches=0,
            n_goals=0,
            log_likelihood=0.0,
            converged=False,
            half_life_minutes=2.8,
        )

    # Ponto inicial
    x0 = np.array([0.08, 0.12, 0.25])

    # Bounds: α ∈ [0.01, 0.5], β ∈ [0.05, 1.0]
    bounds = [(0.01, 0.5), (0.01, 0.5), (0.05, 1.0)]

    result = minimize(
        hawkes_log_likelihood,
        x0,
        args=(sequences,),
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 200, "ftol": 1e-8},
    )

    alpha_self_opt = float(result.x[0])
    alpha_cross_opt = float(result.x[1])
    beta_opt = float(result.x[2])

    return HawkesFitResult(
        alpha_self=alpha_self_opt,
        alpha_cross=alpha_cross_opt,
        beta=beta_opt,
        n_matches=n_matches,
        n_goals=n_goals,
        log_likelihood=float(-result.fun),
        converged=bool(result.success),
        half_life_minutes=float(np.log(2) / beta_opt),
    )


def save_hawkes_params(fit_result: HawkesFitResult, path: Path | None = None) -> Path:
    """Persiste parâmetros calibrados em JSON."""
    if path is None:
        path = settings.lake_root / "artifacts" / "hawkes_params.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(fit_result)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_hawkes_params(path: Path | None = None) -> HawkesParameters:
    """Carrega parâmetros Hawkes calibrados; fallback para defaults."""
    if path is None:
        path = settings.lake_root / "artifacts" / "hawkes_params.json"

    if not path.exists():
        return HawkesParameters()

    try:
        data = json.loads(path.read_text())
        return HawkesParameters(
            alpha_self=data["alpha_self"],
            alpha_cross=data["alpha_cross"],
            beta=data["beta"],
        )
    except (json.JSONDecodeError, KeyError):
        return HawkesParameters()


def run_hawkes_calibration(
    min_season: int = 2010,
    max_season: int = 2026,
    seed: int = 42,
) -> HawkesFitResult:
    """Pipeline completo: constrói sequências → MLE → salva.

    Entrypoint para CLI ou integração com pipelines.
    """
    import structlog

    log = structlog.get_logger()

    log.info("hawkes_calibration_started", min_season=min_season, max_season=max_season)

    sequences = build_goal_sequences(min_season, max_season, seed)
    log.info("hawkes_sequences_built", n_matches=len(sequences),
             n_goals=sum(len(e) for e, _, _, _ in sequences))

    fit = fit_hawkes_mle(sequences=sequences)
    log.info(
        "hawkes_mle_completed",
        alpha_self=round(fit.alpha_self, 4),
        alpha_cross=round(fit.alpha_cross, 4),
        beta=round(fit.beta, 4),
        half_life=round(fit.half_life_minutes, 1),
        stable=fit.is_stable,
        converged=fit.converged,
        log_likelihood=round(fit.log_likelihood, 1),
    )

    path = save_hawkes_params(fit)
    log.info("hawkes_params_saved", path=str(path))

    return fit
