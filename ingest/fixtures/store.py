from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import settings

COMPETITION_PREFIXES = {
    "brasileirao": "brasileirao_",
    "copa_brasil": "copa_brasil_",
}


def _glob_for(competition: str | None) -> list[Path]:
    root = settings.fixtures_path
    if not root.exists():
        return []
    if competition:
        prefix = COMPETITION_PREFIXES.get(competition)
        if not prefix:
            return []
        return list(root.glob(f"{prefix}*.parquet"))
    return list(root.glob("*.parquet"))


def load_fixtures(
    season: int | None = None,
    competition: str | None = None,
) -> pd.DataFrame:
    files = _glob_for(competition)
    if not files:
        return pd.DataFrame()

    if season is not None and competition:
        prefix = COMPETITION_PREFIXES[competition]
        path = settings.fixtures_path / f"{prefix}{season}.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    if season is not None:
        frames = []
        for comp, prefix in COMPETITION_PREFIXES.items():
            path = settings.fixtures_path / f"{prefix}{season}.parquet"
            if path.exists():
                frames.append(pd.read_parquet(path))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def save_fixtures_df(df: pd.DataFrame, competition: str, season: int) -> Path | None:
    if df.empty:
        return None
    prefix = COMPETITION_PREFIXES.get(competition)
    if not prefix:
        raise ValueError(f"Competição desconhecida: {competition}")
    settings.fixtures_path.mkdir(parents=True, exist_ok=True)
    out_path = settings.fixtures_path / f"{prefix}{season}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path
