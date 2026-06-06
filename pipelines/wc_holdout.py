"""Separação treino/holdout por edição da Copa (não temporada de calendário inteira)."""
from __future__ import annotations

import pandas as pd

WC_PHASES = frozenset(
    {"group", "round_16", "quarter", "semi", "third_place", "final"},
)


def wc_holdout_test_df(fixtures_df: pd.DataFrame, edition: int) -> pd.DataFrame:
    """Jogos de validação da edição (ex.: 64 jogos da Copa 2022)."""
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
    """Treino = todos os jogos exceto o holdout da edição (mantém amistosos de 2022, etc.)."""
    holdout = wc_holdout_test_df(fixtures_df, edition)
    if holdout.empty:
        return fixtures_df.sort_values("match_date").copy()
    holdout_idx = set(holdout.index)
    return fixtures_df[~fixtures_df.index.isin(holdout_idx)].sort_values("match_date").copy()
