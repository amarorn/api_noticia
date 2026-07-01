"""CLI: treina coeficientes in-play (momentum + NHPP) usando fixtures históricas + live_ticks.

Uso:
    python -m pipelines.wc_inplay_train [--source fixtures|ticks|both] [--eval-season 2022]

O dataset de treino prioriza fixtures históricas (Copa do Mundo 2010-2022) que têm
volume suficiente (>10k snapshots). Live_ticks são usados como complemento quando
houver volume mínimo (≥100 snapshots).
"""
from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd

from config import settings
from models.wc_inplay_coefficients import (
    InPlayCoefficients,
    MomentumBeta,
    NHPPWeight,
    save_inplay_coefficients,
)
from pipelines.wc_build_timeline import build_timeline_from_fixtures
from pipelines.wc_inplay_ticks_dataset import build_timeline_from_live_ticks
from pipelines.wc_inplay_tune import (
    MOMENTUM_FEATURES,
    _build_feature_matrix,
    _poisson_loglik,
    fit_momentum_mle,
    fit_nhpp_weights,
)

logger = logging.getLogger(__name__)


def _merge_training_sources(
    *,
    min_train_season: int,
    eval_season: int,
    source: str,
    min_ticks_for_live: int = 100,
) -> pd.DataFrame:
    """Combina fixtures históricas e/ou live_ticks para treino.

    Estratégia:
    - Fixtures: sempre incluídas (volume garantido)
    - Live_ticks: só incluídas se ≥ min_ticks_for_live snapshots
    """
    parts: list[pd.DataFrame] = []

    if source in {"fixtures", "both"}:
        fx = build_timeline_from_fixtures(
            min_season=min_train_season,
            max_season=eval_season - 1,
        )
        if not fx.empty:
            fx = fx.copy()
            fx["source"] = "fixtures"
            parts.append(fx)
            logger.info("fixtures_carregadas", n_snapshots=len(fx), n_jogos=fx["match_id"].nunique())

    if source in {"ticks", "both"}:
        ticks = build_timeline_from_live_ticks()
        if not ticks.empty:
            n_ticks = len(ticks)
            n_jogos = ticks["match_id"].nunique()
            logger.info("live_ticks_carregadas", n_snapshots=n_ticks, n_jogos=n_jogos)
            if n_ticks >= min_ticks_for_live:
                ticks = ticks.copy()
                # Normaliza source para compatibilidade
                if "source" not in ticks.columns:
                    ticks["source"] = "live_ticks"
                parts.append(ticks)
                logger.info("live_ticks_incluidas", n_snapshots=n_ticks)
            else:
                logger.warning(
                    "live_ticks_insuficientes",
                    n_ticks=n_ticks,
                    minimo=min_ticks_for_live,
                    acao="usando_apenas_fixtures",
                )

    if not parts:
        return pd.DataFrame()

    df = pd.concat(parts, ignore_index=True)
    # Deduplica: se mesmo match_id+minute existe em ambas, prioriza live_ticks
    if "source" in df.columns:
        source_priority = {"live_ticks": 0, "fixtures": 1}
        df["_priority"] = df["source"].map(source_priority).fillna(2)
        df = df.sort_values("_priority").drop_duplicates(subset=["match_id", "minute"], keep="first")
        df = df.drop(columns=["_priority"])

    return df


def run_inplay_train(
    eval_season: int = 2022,
    min_train_season: int = 2010,
    regularization: float = 0.1,
    verbose: bool = True,
    *,
    source: str = "both",
    min_ticks_for_live: int = 100,
    save_timeline: bool = True,
) -> InPlayCoefficients:
    """Treina coeficientes in-play com fixtures + live_ticks.

    Args:
        eval_season: Season de holdout (não incluída no treino)
        min_train_season: Season mínima para treino
        regularization: L2 penalty para momentum MLE
        source: "fixtures" (só histórico), "ticks" (só ao vivo), "both" (híbrido)
        min_ticks_for_live: Mínimo de live_ticks para incluir no treino
        save_timeline: Se True, salva timeline consolidada em Parquet
    """
    if save_timeline:
        full_timeline = build_timeline_from_fixtures(
            min_season=min_train_season,
            max_season=eval_season,
        )
        if not full_timeline.empty:
            path = save_timeline(full_timeline)
            if verbose:
                print(f"Timeline completa salva: {path} ({len(full_timeline)} snapshots)")

    train_df = _merge_training_sources(
        min_train_season=min_train_season,
        eval_season=eval_season,
        source=source,
        min_ticks_for_live=min_ticks_for_live,
    )

    min_rows = settings.inplay_tune_min_snapshots
    if train_df.empty or len(train_df) < min_rows:
        raise ValueError(
            f"Dataset de treino insuficiente: {len(train_df)} snapshots "
            f"(mínimo {min_rows}, source={source}). "
            f"Rode: import-world-cup --missing-only && run-pipeline gold"
        )

    if verbose:
        src_counts = train_df["source"].value_counts().to_dict() if "source" in train_df.columns else {}
        print(
            f"\nDataset treino ({source}): {len(train_df)} snapshots de "
            f"{train_df['match_id'].nunique()} jogos — {src_counts}"
        )

    # 1. MLE do momentum
    betas, se = fit_momentum_mle(train_df, regularization=regularization)
    if verbose:
        print("\n--- Momentum β's (MLE) ---")
        for i, name in enumerate(MOMENTUM_FEATURES):
            sig = "***" if se[i] > 0 and abs(betas[i] / se[i]) > 1.96 else ""
            print(f"  {name:20s}: β={betas[i]:+.4f} SE={se[i]:.4f} {sig}")

    # 2. MLE do NHPP
    nhpp_results = fit_nhpp_weights(train_df)
    if verbose:
        print("\n--- NHPP weights (MLE) ---")
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

    train_seasons = sorted(train_df["season"].dropna().unique().tolist())

    # Log-likelihood in-sample
    X = _build_feature_matrix(train_df)
    remaining_frac = train_df["remaining_fraction"].values
    obs_home = train_df["remaining_goals_home"].values.astype(float)
    obs_away = train_df["remaining_goals_away"].values.astype(float)
    base_home = 1.35 * remaining_frac
    base_away = 1.10 * remaining_frac
    factor = np.exp(X @ betas)
    in_sample_ll = _poisson_loglik(base_home * factor, obs_home) + _poisson_loglik(
        base_away * factor, obs_away
    )

    # Dataset hash
    from models.wc_inplay_coefficients import compute_dataset_hash
    from pipelines.wc_build_timeline import timeline_path

    tl_path = timeline_path()
    dataset_hash = compute_dataset_hash(tl_path.parent) if tl_path else ""

    coefficients = InPlayCoefficients(
        momentum_betas=momentum_betas,
        nhpp_weights=nhpp_weights,
        train_seasons=train_seasons,
        n_observations=len(train_df),
        in_sample_loglik=round(in_sample_ll, 2),
        dataset_hash=dataset_hash,
    )

    path = save_inplay_coefficients(coefficients)
    if verbose:
        print(f"\nCoeficientes salvos em: {path}")
        print(f"  Observações: {len(train_df)}")
        print(f"  Log-likelihood in-sample: {in_sample_ll:.2f}")

    return coefficients


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Treina coeficientes in-play (momentum + NHPP) com fixtures + live_ticks"
    )
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--min-train-season", type=int, default=2010)
    parser.add_argument("--regularization", type=float, default=0.1)
    parser.add_argument(
        "--source",
        choices=("fixtures", "ticks", "both"),
        default="both",
        help="fixtures=só histórico; ticks=só ao vivo; both=híbrido (default)",
    )
    parser.add_argument("--min-ticks-for-live", type=int, default=100)
    parser.add_argument("--no-save-timeline", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    args = parser.parse_args()

    try:
        run_inplay_train(
            eval_season=args.eval_season,
            min_train_season=args.min_train_season,
            regularization=args.regularization,
            verbose=args.verbose,
            source=args.source,
            min_ticks_for_live=args.min_ticks_for_live,
            save_timeline=not args.no_save_timeline,
        )
        return 0
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
