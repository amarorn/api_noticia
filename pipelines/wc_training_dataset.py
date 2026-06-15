"""Dataset de treino WC — Opção B: labels só Copa, features com histórico completo."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import structlog

from config import settings
from pipelines.wc_holdout import WC_PHASES, _wc_holdout_test_by_edition, wc_holdout_train_df

logger = structlog.get_logger()

WC_COPA_COMPETITION = "Copa do Mundo"


def is_wc_copa_match(row: pd.Series) -> bool:
    """True se o jogo pertence à Copa do Mundo (label de treino)."""
    comp = row.get("competition")
    if isinstance(comp, str) and comp.strip() == WC_COPA_COMPETITION:
        return True
    phase = row.get("phase")
    if isinstance(phase, str) and phase in WC_PHASES:
        return True
    return False


def filter_wc_copa_labels(fixtures_df: pd.DataFrame) -> pd.DataFrame:
    """Filtra linhas elegíveis como label de treino Copa (exclui amistosos/eliminatórias)."""
    if fixtures_df.empty:
        return fixtures_df
    mask = fixtures_df.apply(is_wc_copa_match, axis=1)
    return fixtures_df[mask].copy().reset_index(drop=True)


def wc_temporal_train_val_test_split(
    copa_df: pd.DataFrame,
    *,
    train_ratio: float | None = None,
    val_ratio: float | None = None,
    test_ratio: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split cronológico 80/10/10 (ou ratios configurados) sem embaralhar."""
    tr = settings.wc_train_split_ratio if train_ratio is None else train_ratio
    vr = settings.wc_val_split_ratio if val_ratio is None else val_ratio
    te = settings.wc_test_split_ratio if test_ratio is None else test_ratio
    total_ratio = tr + vr + te
    if total_ratio <= 0:
        tr, vr, te = 0.8, 0.1, 0.1
        total_ratio = 1.0
    tr, vr, te = tr / total_ratio, vr / total_ratio, te / total_ratio

    df = copa_df.sort_values("match_date").reset_index(drop=True)
    n = len(df)
    if n == 0:
        empty = df.copy()
        return empty, empty, empty

    train_end = int(n * tr)
    val_end = int(n * (tr + vr))

    if n >= 3:
        train_end = max(1, min(train_end, n - 2))
        val_end = max(train_end + 1, min(val_end, n - 1))
    elif n == 2:
        train_end = 1
        val_end = 1

    train = df.iloc[:train_end].copy()
    val = df.iloc[train_end:val_end].copy()
    test = df.iloc[val_end:].copy()
    return train, val, test


def wc_temporal_train_test_split(
    copa_df: pd.DataFrame,
    train_ratio: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compat: retorna treino e restante (val + test)."""
    train, val, test = wc_temporal_train_val_test_split(copa_df, train_ratio=train_ratio)
    rest = pd.concat([val, test], ignore_index=True) if not val.empty or not test.empty else test
    return train, rest


def wc_split_train_val_test(
    fixtures_df: pd.DataFrame,
    edition: int | None,
    *,
    copa_labels_only: bool | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Define treino (80%), validação (10%) e teste (10%) conforme wc_holdout_mode."""
    use_copa_only = (
        settings.wc_train_labels_copa_only
        if copa_labels_only is None
        else copa_labels_only
    )
    df = fixtures_df.sort_values("match_date").copy()
    mode = (settings.wc_holdout_mode or "temporal").strip().lower()

    if mode == "edition" and edition is not None:
        train = wc_holdout_train_df(df, edition)
        test = _wc_holdout_test_by_edition(df, edition)
        if use_copa_only:
            train = filter_wc_copa_labels(train)
            test = filter_wc_copa_labels(test)
        val = test.copy()
        return train, val, test

    pool = filter_wc_copa_labels(df) if use_copa_only else df
    train, val, test = wc_temporal_train_val_test_split(pool)
    logger.info(
        "wc_temporal_split",
        mode=mode,
        train_ratio=settings.wc_train_split_ratio,
        val_ratio=settings.wc_val_split_ratio,
        test_ratio=settings.wc_test_split_ratio,
        train_rows=len(train),
        val_rows=len(val),
        test_rows=len(test),
        total=len(pool),
    )
    return train, val, test


def wc_split_train_test(
    fixtures_df: pd.DataFrame,
    edition: int | None,
    *,
    copa_labels_only: bool | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compat: treino e holdout (val + test)."""
    train, val, test = wc_split_train_val_test(fixtures_df, edition, copa_labels_only=copa_labels_only)
    holdout = pd.concat([val, test], ignore_index=True) if not val.empty or not test.empty else test
    return train, holdout


def wc_training_label_df(
    fixtures_df: pd.DataFrame,
    edition: int | None,
    *,
    copa_labels_only: bool | None = None,
) -> pd.DataFrame:
    """Linhas usadas como labels de treino (80% cronológico ou pré-holdout por edição)."""
    train, _, _ = wc_split_train_val_test(fixtures_df, edition, copa_labels_only=copa_labels_only)
    return train


def wc_validation_label_df(
    fixtures_df: pd.DataFrame,
    edition: int | None,
    *,
    copa_labels_only: bool | None = None,
) -> pd.DataFrame:
    """Linhas de validação (10% cronológico) — blend, calibrador, tune."""
    _, val, _ = wc_split_train_val_test(fixtures_df, edition, copa_labels_only=copa_labels_only)
    return val


def wc_test_label_df(
    fixtures_df: pd.DataFrame,
    edition: int | None,
    *,
    copa_labels_only: bool | None = None,
) -> pd.DataFrame:
    """Linhas de teste (10% cronológico) — métricas finais de holdout."""
    _, _, test = wc_split_train_val_test(fixtures_df, edition, copa_labels_only=copa_labels_only)
    return test


def load_wc_fixtures_for_training() -> pd.DataFrame:
    """Pool completo para features (Elo, forma, xG) — inclui FIFA/Sofascore se configurado."""
    from ingest.fixtures.world_cup import load_wc_fixtures

    return load_wc_fixtures(include_fifa=settings.wc_train_include_fifa_history)


def export_wc_copa_labels_dataset(
    fixtures_df: pd.DataFrame | None = None,
    *,
    path: Path | None = None,
    edition: int | None = None,
) -> dict[str, Path]:
    """Persiste gold Copa: completo + split treino (80%) / val (10%) / test (10%)."""
    df = fixtures_df if fixtures_df is not None else load_wc_fixtures_for_training()
    copa = filter_wc_copa_labels(df)
    train, val, test = wc_split_train_val_test(df, edition or settings.wc_validation_season)

    base = path or (settings.gold_path / "wc")
    base.mkdir(parents=True, exist_ok=True)
    paths = {
        "all": base / "copa_labels.parquet",
        "train": base / "copa_labels_train.parquet",
        "val": base / "copa_labels_val.parquet",
        "test": base / "copa_labels_test.parquet",
    }
    copa.to_parquet(paths["all"], index=False)
    train.to_parquet(paths["train"], index=False)
    val.to_parquet(paths["val"], index=False)
    test.to_parquet(paths["test"], index=False)
    logger.info(
        "wc_copa_labels_exported",
        all_rows=len(copa),
        train_rows=len(train),
        val_rows=len(val),
        test_rows=len(test),
        train_ratio=settings.wc_train_split_ratio,
        val_ratio=settings.wc_val_split_ratio,
        test_ratio=settings.wc_test_split_ratio,
        mode=settings.wc_holdout_mode,
    )
    return paths


def training_dataset_summary(fixtures_df: pd.DataFrame, edition: int | None) -> dict:
    """Resumo para logs/MLflow: pool de features vs labels de treino."""
    ed = edition if edition is not None else settings.wc_validation_season
    train, val, test = wc_split_train_val_test(fixtures_df, ed)
    copa_all = filter_wc_copa_labels(fixtures_df)
    return {
        "feature_pool_rows": len(fixtures_df),
        "copa_rows_total": len(copa_all),
        "train_label_rows": len(train),
        "val_rows": len(val),
        "test_rows": len(test),
        "holdout_rows": len(val) + len(test),
        "holdout_edition": ed if settings.wc_holdout_mode == "edition" else None,
        "holdout_mode": settings.wc_holdout_mode,
        "train_split_ratio": settings.wc_train_split_ratio,
        "val_split_ratio": settings.wc_val_split_ratio,
        "test_split_ratio": settings.wc_test_split_ratio,
        "labels_copa_only": settings.wc_train_labels_copa_only,
        "include_fifa_history": settings.wc_train_include_fifa_history,
    }
