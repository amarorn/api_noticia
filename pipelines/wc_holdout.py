"""Separação treino/holdout por edição da Copa (não temporada de calendário inteira)."""
from __future__ import annotations

import pandas as pd

WC_PHASES = frozenset(
    {"group", "round_16", "quarter", "semi", "third_place", "final"},
)


def _wc_holdout_test_by_edition(fixtures_df: pd.DataFrame, edition: int) -> pd.DataFrame:
    """Holdout clássico: todos os jogos da edição (ex.: Copa 2022)."""
    df = fixtures_df.sort_values("match_date")
    if "competition" in df.columns:
        wc = df[(df["season"] == edition) & (df["competition"] == "Copa do Mundo")]
        if not wc.empty:
            return wc.copy()

    by_phase = df[(df["season"] == edition) & (df["phase"].isin(WC_PHASES))]
    if len(by_phase) >= 32:
        return by_phase.copy()

    return df[df["season"] == edition].copy()


def wc_holdout_train_df(fixtures_df: pd.DataFrame, edition: int) -> pd.DataFrame:
    """Treino = todos os jogos exceto o holdout da edição (sem filtro Copa — ver wc_training_label_df)."""
    holdout = _wc_holdout_test_by_edition(fixtures_df, edition)
    if holdout.empty:
        return fixtures_df.sort_values("match_date").copy()
    holdout_idx = set(holdout.index)
    return fixtures_df[~fixtures_df.index.isin(holdout_idx)].sort_values("match_date").copy()


def wc_holdout_test_df(fixtures_df: pd.DataFrame, edition: int) -> pd.DataFrame:
    """Jogos de teste/holdout final (10% cronológico ou edição completa, conforme config)."""
    from pipelines.wc_training_dataset import wc_test_label_df

    return wc_test_label_df(fixtures_df, edition)
