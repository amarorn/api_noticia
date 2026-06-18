"""Calibração de λ pré-jogo com xG rolling Sofascore."""
from __future__ import annotations

from datetime import datetime

from models.poisson_wc import XgCalibration
from pipelines.wc_sofascore_features import team_rolling_stats
from ingest.sofascore.stats_dataset import load_match_stats_history


def build_xg_calibration(
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    stats_df=None,
) -> XgCalibration | None:
    """Monta XgCalibration a partir dos últimos jogos Sofascore das seleções."""
    history = stats_df if stats_df is not None else load_match_stats_history()
    if history.empty:
        return None

    if before_date is not None:
        cutoff = before_date
        df = history.copy()
        df["_dt"] = df["match_date"]
        try:
            import pandas as pd

            df["_dt"] = pd.to_datetime(df["match_date"], utc=True)
            df = df[df["_dt"] < cutoff]
        except Exception:
            pass
        history = df.drop(columns=["_dt"], errors="ignore")
        if history.empty:
            return None

    home_stats = team_rolling_stats(history, home_team)
    away_stats = team_rolling_stats(history, away_team)
    if home_stats is None and away_stats is None:
        return None

    return XgCalibration(
        home_xg_for=home_stats.xg_for if home_stats else None,
        home_xg_against=home_stats.xg_against if home_stats else None,
        away_xg_for=away_stats.xg_for if away_stats else None,
        away_xg_against=away_stats.xg_against if away_stats else None,
    )


__all__ = ["build_xg_calibration"]
