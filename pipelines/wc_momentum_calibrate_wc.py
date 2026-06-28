"""Calibra coeficientes de momentum e Hawkes com ticks reais da Copa do Mundo.

Usa match_states.parquet (silver) para:
  1. Inferir eventos de gol por diferença de placar entre ticks consecutivos
  2. Estimar pesos do perfil NHPP (gols observados × minuto)
  3. Ajustar α_self, α_cross, β do processo Hawkes via MLE (scipy.optimize)
  4. Estimar β's do momentum por regressão log-linear

Salva resultado em inplay_coefficients.json.

CLI: calibrate-wc-momentum [--holdout-events N]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from models.wc_inplay_coefficients import (
    InPlayCoefficients,
    MomentumBeta,
    NHPPWeight,
    save_inplay_coefficients,
)
from pipelines.inplay_match_states import MATCH_STATES_PATH

logger = logging.getLogger(__name__)

# Buckets NHPP padrão (limites dos intervalos)
_NHPP_BINS = [0, 15, 30, 45, 60, 75, 90]
_NHPP_LABELS = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]


# ---------------------------------------------------------------------------
# Extração de eventos de gol dos ticks
# ---------------------------------------------------------------------------

def extract_goal_events(states: pd.DataFrame) -> pd.DataFrame:
    """Infere eventos de gol comparando placar entre ticks consecutivos.

    Args:
        states: match_states.parquet com colunas event_id, minute,
                home_score, away_score.

    Returns:
        DataFrame com colunas: event_id, minute, team ("home"/"away").
    """
    df = states.copy()
    for col in ("event_id", "minute", "home_score", "away_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["event_id", "minute", "home_score", "away_score"])
    df = df.sort_values(["event_id", "minute"]).reset_index(drop=True)

    goals: list[dict[str, Any]] = []
    for event_id, group in df.groupby("event_id"):
        group = group.reset_index(drop=True)
        prev_h = group["home_score"].shift(1).fillna(method="bfill")
        prev_a = group["away_score"].shift(1).fillna(method="bfill")
        home_goals = group[group["home_score"] > prev_h]
        away_goals = group[group["away_score"] > prev_a]
        for _, row in home_goals.iterrows():
            goals.append({"event_id": int(event_id), "minute": float(row["minute"]), "team": "home"})
        for _, row in away_goals.iterrows():
            goals.append({"event_id": int(event_id), "minute": float(row["minute"]), "team": "away"})

    return pd.DataFrame(goals) if goals else pd.DataFrame(columns=["event_id", "minute", "team"])


# ---------------------------------------------------------------------------
# Calibração do perfil NHPP
# ---------------------------------------------------------------------------

def calibrate_nhpp_weights(goal_events: pd.DataFrame) -> list[NHPPWeight]:
    """Estima pesos NHPP contando gols por bucket temporal.

    Normaliza para que a média ponderada dos pesos seja 1.0 (referência = uniforme).

    Args:
        goal_events: DataFrame com coluna 'minute'.

    Returns:
        Lista de NHPPWeight calibrados.
    """
    if goal_events.empty:
        # Pesos default da literatura (Ref: Karlis & Ntzoufras 2003)
        defaults = [0.84, 0.96, 1.04, 1.06, 1.10, 1.20]
        return [
            NHPPWeight(start_min=_NHPP_BINS[i], end_min=_NHPP_BINS[i + 1], weight=defaults[i])
            for i in range(len(_NHPP_LABELS))
        ]

    minutes = goal_events["minute"].clip(0, 89.9)
    total_goals = len(minutes)
    weights: list[NHPPWeight] = []

    for i in range(len(_NHPP_LABELS)):
        lo, hi = _NHPP_BINS[i], _NHPP_BINS[i + 1]
        duration = hi - lo
        n_goals = ((minutes >= lo) & (minutes < hi)).sum()
        # Rate observada vs esperada uniforme (total_goals / 90 por minuto)
        expected_uniform = total_goals * duration / 90
        weight = float(n_goals / expected_uniform) if expected_uniform > 0 else 1.0
        std_err = float(np.sqrt(n_goals) / expected_uniform) if expected_uniform > 0 else 0.0
        weights.append(NHPPWeight(
            start_min=lo,
            end_min=hi,
            weight=round(weight, 4),
            std_error=round(std_err, 4),
        ))

    return weights


# ---------------------------------------------------------------------------
# Calibração Hawkes (MLE)
# ---------------------------------------------------------------------------

def _hawkes_loglik(
    params: np.ndarray,
    goal_events_per_match: list[pd.DataFrame],
    mu_home: float = 1.3 / 90,
    mu_away: float = 1.1 / 90,
    T: float = 90.0,
) -> float:
    """Log-verossimilhança negativa do processo Hawkes bidimensional.

    Parâmetros:
        params = [alpha_self, alpha_cross, beta]

    Model: λ_i(t) = μ_i + Σ_{j < t} [α_s·I(same) + α_c·I(cross)] · exp(-β·(t - t_j))
    """
    alpha_s, alpha_c, beta = params
    if alpha_s < 0 or alpha_c < 0 or beta <= 0:
        return 1e10

    total_loglik = 0.0

    for events in goal_events_per_match:
        if events.empty:
            continue

        for t_idx, row in events.iterrows():
            t = float(row["minute"])
            team = row["team"]
            mu = mu_home if team == "home" else mu_away

            # Intensidade no momento do gol
            past = events[events.index < t_idx]
            excitement = sum(
                (alpha_s if r["team"] == team else alpha_c) * np.exp(-beta * (t - r["minute"]))
                for _, r in past.iterrows()
            )
            intensity = mu + excitement
            if intensity <= 0:
                return 1e10
            total_loglik += np.log(intensity)

        # Integral da intensidade (compensador)
        all_minutes = events["minute"].values
        for t_j, team_j in zip(all_minutes, events["team"].values):
            alpha = alpha_s if team_j == team_j else alpha_c  # self/cross handled below
            # Contribuição de cada gol ao integral: integral_t_j^T [α exp(-β(t-t_j))] dt
            # = (α/β)(1 - exp(-β(T - t_j)))
            contrib_s = (alpha_s / beta) * (1 - np.exp(-beta * (T - t_j)))
            contrib_c = (alpha_c / beta) * (1 - np.exp(-beta * (T - t_j)))
            # Para home self, away cross e vice-versa
            total_loglik -= (contrib_s + contrib_c) / 2  # aproximação simples

        # Baseline
        total_loglik -= (mu_home + mu_away) * T

    return -total_loglik  # negativo para minimização


def calibrate_hawkes(
    goal_events: pd.DataFrame,
    min_matches: int = 10,
) -> dict[str, float]:
    """Estima α_self, α_cross, β do processo Hawkes via MLE.

    Args:
        goal_events: DataFrame com event_id, minute, team.
        min_matches: mínimo de partidas com gols para ajuste.

    Returns:
        Dict {"alpha_self": ..., "alpha_cross": ..., "beta": ...}.
    """
    # Defaults da literatura (Ref: Boshnakov et al 2017)
    defaults = {"alpha_self": 0.08, "alpha_cross": 0.12, "beta": 0.25}

    if goal_events.empty:
        return defaults

    matches = [g for _, g in goal_events.groupby("event_id") if len(g) >= 1]
    if len(matches) < min_matches:
        logger.warning("hawkes_poucos_jogos", n_jogos=len(matches), minimo=min_matches)
        return defaults

    try:
        from scipy.optimize import minimize

        x0 = np.array([0.08, 0.12, 0.25])
        bounds = [(0.001, 0.5), (0.001, 0.5), (0.05, 2.0)]
        result = minimize(
            _hawkes_loglik,
            x0,
            args=(matches,),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 200, "ftol": 1e-8},
        )
        if result.success:
            a_s, a_c, beta = result.x
            logger.info(
                "hawkes_calibrado",
                alpha_self=round(a_s, 4),
                alpha_cross=round(a_c, 4),
                beta=round(beta, 4),
                loglik=-result.fun,
            )
            return {
                "alpha_self": round(float(a_s), 4),
                "alpha_cross": round(float(a_c), 4),
                "beta": round(float(beta), 4),
            }
    except Exception as exc:
        logger.warning("hawkes_mle_falhou", error=str(exc))

    return defaults


# ---------------------------------------------------------------------------
# Betas de momentum (regressão log-linear)
# ---------------------------------------------------------------------------

def calibrate_momentum_betas(states: pd.DataFrame) -> list[MomentumBeta]:
    """Estima betas do momentum por regressão linear do log(gols_observados).

    Usa correlação entre features de contexto (goal_diff, minuto, n_red_cards)
    e desvio do placar final em relação ao esperado pelo Poisson.

    Produz betas para as variáveis principais do modelo de momentum.
    """
    df = states.copy()
    df = df[df["y_final"].notna()].copy()
    if len(df) < 50:
        # Retornar betas nulos (momentum usa constantes padrão da Fase 1)
        return []

    try:
        import statsmodels.api as sm

        for col in ("minute", "home_score", "away_score", "prob_final_home", "prob_final_away"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["minute", "home_score", "away_score"])

        df["goal_diff"] = df["home_score"] - df["away_score"]
        df["late_game"] = (df["minute"] >= 75).astype(float)
        df["y_home_wins"] = (df["y_final"] == "1").astype(float)

        # Modelo simples: logit(P(home win)) ~ goal_diff + minute_norm + late_game
        df["minute_norm"] = df["minute"] / 90.0
        df = df.dropna(subset=["y_home_wins", "goal_diff", "minute_norm", "late_game"])

        if len(df) < 50:
            return []

        X = sm.add_constant(df[["goal_diff", "minute_norm", "late_game"]])
        model = sm.Logit(df["y_home_wins"], X).fit(disp=False)

        betas: list[MomentumBeta] = []
        for name in ["goal_diff", "minute_norm", "late_game"]:
            coef = float(model.params.get(name, 0.0))
            se = float(model.bse.get(name, 1.0))
            betas.append(MomentumBeta(name=name, value=round(coef, 4), std_error=round(se, 4)))

        sig = [b for b in betas if b.significant]
        logger.info("momentum_betas_estimados", n_betas=len(betas), n_significativos=len(sig))
        return betas

    except Exception as exc:
        logger.warning("momentum_beta_falhou", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run_wc_calibration(
    holdout_events: int = 0,
    states_path: Path | None = None,
) -> dict[str, Any]:
    """Calibra todos os coeficientes in-play com dados reais da Copa.

    Args:
        holdout_events: reservar os últimos N event_ids para holdout.
        states_path: caminho alternativo do match_states.parquet.

    Returns:
        Dict com sumário dos coeficientes calibrados.
    """
    path = states_path or MATCH_STATES_PATH
    if not path.exists():
        return {"error": f"match_states ausente: {path}"}

    states = pd.read_parquet(path)
    n_events = int(states["event_id"].nunique()) if "event_id" in states.columns else 0
    logger.info("calibracao_iniciada", n_ticks=len(states), n_eventos=n_events)

    # Holdout opcional
    if holdout_events > 0 and "event_id" in states.columns:
        all_ids = sorted(states["event_id"].dropna().unique())
        train_ids = set(all_ids[:-holdout_events])
        states = states[states["event_id"].isin(train_ids)]

    # Extrair gols
    goal_events = extract_goal_events(states)
    n_goals = len(goal_events)
    logger.info("gols_extraidos", n_gols=n_goals)

    # 1. Pesos NHPP
    nhpp_weights = calibrate_nhpp_weights(goal_events)

    # 2. Hawkes
    hawkes = calibrate_hawkes(goal_events)

    # 3. Betas do momentum
    momentum_betas = calibrate_momentum_betas(states)

    # Construir coeficientes
    extra_betas = [
        MomentumBeta(
            name="hawkes_alpha_self",
            value=hawkes["alpha_self"],
            std_error=0.0,
        ),
        MomentumBeta(
            name="hawkes_alpha_cross",
            value=hawkes["alpha_cross"],
            std_error=0.0,
        ),
        MomentumBeta(
            name="hawkes_beta",
            value=hawkes["beta"],
            std_error=0.0,
        ),
    ]

    all_betas = momentum_betas + extra_betas

    coefficients = InPlayCoefficients(
        momentum_betas=all_betas,
        nhpp_weights=nhpp_weights,
        train_seasons=[2026],
        n_observations=len(states),
        dataset_hash=str(hash(str(path.stat().st_mtime) if path.exists() else "")),
    )

    artifact_path = save_inplay_coefficients(coefficients)
    logger.info("coeficientes_salvos", path=str(artifact_path))

    return {
        "artifact_path": str(artifact_path),
        "n_ticks": len(states),
        "n_events": n_events,
        "n_goals_used": n_goals,
        "nhpp_weights": {w.start_min: w.weight for w in nhpp_weights},
        "hawkes": hawkes,
        "momentum_betas": [
            {"name": b.name, "value": b.value, "significant": b.significant}
            for b in momentum_betas
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calibra coeficientes momentum/Hawkes com ticks reais da Copa"
    )
    parser.add_argument("--holdout-events", type=int, default=0,
                        help="N últimos event_ids reservados para holdout")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_wc_calibration(holdout_events=args.holdout_events)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
