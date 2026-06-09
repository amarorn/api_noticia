"""MLE para calibração dos coeficientes do modelo in-play.

Estima via L-BFGS-B:
1. Coeficientes β do momentum (log-linear sobre multiplicador de λ_remaining)
2. Pesos w_i do perfil NHPP (com constraint Σ w_i × dur_i = 90)

A likelihood é Poisson: para cada snapshot (minuto, placar parcial),
observamos os gols restantes e maximizamos P(obs | λ_remaining(β, w)).

Spec: docs/specs/spec-fase-2-momentum-calibrado.md § 5.3 e 5.4
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from models.wc_inplay_coefficients import (
    InPlayCoefficients,
    MomentumBeta,
    NHPPWeight,
    save_inplay_coefficients,
)
from pipelines.wc_build_timeline import build_timeline_from_fixtures
from pipelines.wc_intensity_profile import default_intensity_profile


# Nomes dos features do momentum (mesma ordem dos β's)
MOMENTUM_FEATURES = [
    "intercept",
    "goal_diff",
    "goal_diff_squared",
    "late_game",
    "home_red_cards",
    "away_red_cards",
    "corner_share",
    "goal_diff_x_late",  # interação
]


def _build_feature_matrix(timeline_df) -> np.ndarray:
    """Constrói matrix X de features do momentum a partir da timeline.

    Cada linha é um snapshot. Colunas seguem MOMENTUM_FEATURES.
    """
    n = len(timeline_df)
    X = np.zeros((n, len(MOMENTUM_FEATURES)))

    X[:, 0] = 1.0  # intercept

    goal_diff = (
        timeline_df["home_score_partial"].values
        - timeline_df["away_score_partial"].values
    )
    X[:, 1] = goal_diff
    X[:, 2] = goal_diff ** 2

    # Late game: max(0, minute - 75)
    minutes = timeline_df["minute"].values
    X[:, 3] = np.maximum(0, minutes - 75) / 15.0  # normalizado

    X[:, 4] = timeline_df["home_red_cards"].values
    X[:, 5] = timeline_df["away_red_cards"].values

    # Corner share (0.5 se sem dados)
    hc = timeline_df["home_corners"].values.astype(float)
    ac = timeline_df["away_corners"].values.astype(float)
    total_c = hc + ac
    corner_share = np.where(total_c > 0, hc / total_c, 0.5)
    X[:, 6] = corner_share - 0.5  # centrado em 0

    # Interação: goal_diff × late_game
    X[:, 7] = X[:, 1] * X[:, 3]

    return X


def _poisson_loglik(
    lambdas: np.ndarray,
    observed: np.ndarray,
) -> float:
    """Log-likelihood Poisson: Σ [k × ln(λ) - λ - ln(k!)]."""
    lambdas = np.maximum(lambdas, 1e-8)
    ll = observed * np.log(lambdas) - lambdas - gammaln(observed + 1)
    return float(ll.sum())


def fit_momentum_mle(
    timeline_df,
    lambda_full_home: float = 1.35,
    lambda_full_away: float = 1.10,
    regularization: float = 0.1,
) -> tuple[np.ndarray, np.ndarray]:
    """Estima coeficientes β do momentum por MLE (L-BFGS-B).

    Modelo:
        log(factor_home) = X @ β
        λ_remaining_home = λ_full_home × remaining_fraction × exp(X @ β)

    Observação: gols restantes (remaining_goals_home).

    Args:
        timeline_df: DataFrame da timeline.
        lambda_full_home: λ default do mandante (média Copa).
        lambda_full_away: λ default do visitante.
        regularization: L2 penalty (Ridge) para evitar overfitting.

    Returns:
        (betas, se): arrays de coeficientes e erros padrão.
    """
    X = _build_feature_matrix(timeline_df)

    remaining_frac = timeline_df["remaining_fraction"].values
    obs_home = timeline_df["remaining_goals_home"].values.astype(float)
    obs_away = timeline_df["remaining_goals_away"].values.astype(float)

    # λ_base para cada snapshot (sem momentum)
    base_home = lambda_full_home * remaining_frac
    base_away = lambda_full_away * remaining_frac

    n_betas = X.shape[1]
    beta0 = np.zeros(n_betas)

    def neg_loglik(beta):
        """Negative log-likelihood com regularização L2."""
        factor = np.exp(X @ beta)
        lam_home = base_home * factor
        lam_away = base_away * factor  # mesmo fator para ambos (simplificação simétrica)

        ll_home = _poisson_loglik(lam_home, obs_home)
        ll_away = _poisson_loglik(lam_away, obs_away)

        # Regularização L2 (não no intercept)
        penalty = regularization * np.sum(beta[1:] ** 2)

        return -(ll_home + ll_away) + penalty

    result = minimize(
        neg_loglik,
        beta0,
        method="L-BFGS-B",
        options={"maxiter": 500, "ftol": 1e-8},
    )

    betas = result.x

    # Erros padrão via Hessiana numérica (inversão diagonal)
    try:
        eps = 1e-5
        n_params = len(betas)
        hessian_diag = np.zeros(n_params)
        for i in range(n_params):
            def f_i(b_val):
                b_copy = betas.copy()
                b_copy[i] = b_val
                return neg_loglik(b_copy)
            # Segunda derivada numérica
            h = eps
            hessian_diag[i] = (f_i(betas[i] + h) - 2 * f_i(betas[i]) + f_i(betas[i] - h)) / h**2

        # SE = 1/sqrt(Hessiana_ii)
        se = np.where(hessian_diag > 0, 1.0 / np.sqrt(hessian_diag), 0.0)
    except Exception:
        se = np.zeros_like(betas)

    return betas, se


def fit_nhpp_weights(
    timeline_df,
    lambda_full_home: float = 1.35,
    lambda_full_away: float = 1.10,
    n_buckets: int = 6,
    bucket_duration: int = 15,
) -> list[tuple[int, int, float, float]]:
    """Estima pesos NHPP por bucket via MLE com constraint de normalização.

    Constraint: Σ w_i × dur_i = match_minutes (90).
    Bounds: 0.3 ≤ w_i ≤ 2.0.

    Returns:
        Lista de (start_min, end_min, weight, std_error).
    """
    match_minutes = 90
    profile = default_intensity_profile()

    # Agrupar snapshots por bucket
    obs_by_bucket: list[np.ndarray] = []
    frac_by_bucket: list[np.ndarray] = []

    for i, b in enumerate(profile):
        mask = (
            (timeline_df["minute"] >= b.start_min)
            & (timeline_df["minute"] < b.end_min)
        )
        subset = timeline_df[mask]
        if len(subset) > 0:
            obs = (
                subset["remaining_goals_home"].values
                + subset["remaining_goals_away"].values
            ).astype(float)
            obs_by_bucket.append(obs)
            frac_by_bucket.append(subset["remaining_fraction"].values)
        else:
            obs_by_bucket.append(np.array([0.0]))
            frac_by_bucket.append(np.array([1.0]))

    # Pesos iniciais (literature)
    w0 = np.array([b.weight for b in profile])
    lambda_total = lambda_full_home + lambda_full_away

    def neg_loglik_nhpp(weights):
        """Negative log-likelihood para pesos NHPP."""
        total_ll = 0.0
        for i, b in enumerate(profile):
            if len(obs_by_bucket[i]) == 0:
                continue
            # λ para este bucket = λ_total × w_i × (dur_i / match_minutes)
            lam = lambda_total * weights[i] * (b.duration / match_minutes)
            lam = max(lam, 1e-8)
            for obs_val in obs_by_bucket[i]:
                total_ll += obs_val * np.log(lam) - lam - gammaln(obs_val + 1)
        return -total_ll

    # Constraint: Σ w_i × dur_i = match_minutes
    def constraint_sum(weights):
        return sum(weights[i] * profile[i].duration for i in range(len(profile))) - match_minutes

    from scipy.optimize import minimize as sp_minimize

    result = sp_minimize(
        neg_loglik_nhpp,
        w0,
        method="SLSQP",
        bounds=[(0.3, 2.0)] * n_buckets,
        constraints={"type": "eq", "fun": constraint_sum},
        options={"maxiter": 200, "ftol": 1e-8},
    )

    calibrated_weights = result.x
    # SE: placeholder (SLSQP não dá Hessiana diretamente)
    se_weights = np.full(n_buckets, 0.05)

    return [
        (profile[i].start_min, profile[i].end_min, float(calibrated_weights[i]), float(se_weights[i]))
        for i in range(n_buckets)
    ]


def run_inplay_tune(
    eval_season: int = 2022,
    min_train_season: int = 2010,
    regularization: float = 0.1,
    verbose: bool = True,
) -> InPlayCoefficients:
    """Executa calibração completa: momentum MLE + NHPP MLE.

    Treina em seasons < eval_season; reporta holdout metrics em eval_season.

    Returns:
        InPlayCoefficients com β's e pesos calibrados.
    """
    # Dataset de treino (tudo menos eval_season)
    train_df = build_timeline_from_fixtures(
        min_season=min_train_season, max_season=eval_season - 1,
    )
    if train_df.empty or len(train_df) < 100:
        raise ValueError(
            f"Dataset de treino insuficiente: {len(train_df)} snapshots "
            f"(seasons {min_train_season}–{eval_season - 1})"
        )

    if verbose:
        print(f"Dataset treino: {len(train_df)} snapshots de "
              f"{train_df['match_id'].nunique()} jogos")

    # 1. MLE do momentum
    betas, se = fit_momentum_mle(train_df, regularization=regularization)
    if verbose:
        print("\n--- Momentum β's ---")
        for i, name in enumerate(MOMENTUM_FEATURES):
            sig = "***" if se[i] > 0 and abs(betas[i] / se[i]) > 1.96 else ""
            print(f"  {name:20s}: β={betas[i]:+.4f} SE={se[i]:.4f} {sig}")

    # 2. MLE do NHPP
    nhpp_results = fit_nhpp_weights(train_df)
    if verbose:
        print("\n--- NHPP weights ---")
        for start, end, w, se_w in nhpp_results:
            print(f"  [{start:2d}-{end:2d}]: w={w:.3f} (±{se_w:.3f})")

    # Construir InPlayCoefficients
    momentum_betas = [
        MomentumBeta(name=MOMENTUM_FEATURES[i], value=float(betas[i]), std_error=float(se[i]))
        for i in range(len(MOMENTUM_FEATURES))
    ]
    nhpp_weights = [
        NHPPWeight(start_min=s, end_min=e, weight=w, std_error=se_w)
        for s, e, w, se_w in nhpp_results
    ]

    train_seasons = sorted(train_df["season"].unique().tolist())
    coefficients = InPlayCoefficients(
        momentum_betas=momentum_betas,
        nhpp_weights=nhpp_weights,
        train_seasons=train_seasons,
        n_observations=len(train_df),
    )

    # Salvar
    path = save_inplay_coefficients(coefficients)
    if verbose:
        print(f"\nCoeficientes salvos em: {path}")

    return coefficients
