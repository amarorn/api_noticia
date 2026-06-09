"""Pipeline para construir dataset timeline minuto-a-minuto para calibração in-play.

Como não temos dados de minuto de cada gol na nossa base, geramos snapshots
sintéticos para cada jogo usando distribuição proporcional ao perfil NHPP.
Para cada snapshot (minuto fixo), calculamos:
- Gols esperados já marcados até aquele minuto (proporcional ao NHPP)
- Gols restantes observados (total - parciais arredondados)
- Estado de eventos (vermelhos, escanteios, etc. — distribuição uniforme)

Isso permite calibrar os coeficientes do momentum via MLE: encontrar β's que
maximizam a likelihood dos gols restantes observados dado o estado no snapshot.

Spec: docs/specs/spec-fase-2-momentum-calibrado.md § 5.1
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from pipelines.wc_intensity_profile import default_intensity_profile


# Minutos de snapshot para avaliação
SNAPSHOT_MINUTES = [15, 30, 45, 60, 75, 85]


def _nhpp_cumulative_fraction(minute: int, match_minutes: int = 90) -> float:
    """Fração cumulativa de gols esperados até o minuto dado, segundo perfil NHPP."""
    profile = default_intensity_profile()
    total_weighted = sum(b.weight * b.duration for b in profile)
    cumul = 0.0
    for b in profile:
        start = b.start_min
        end = min(b.end_min, minute)
        if start < end:
            cumul += b.weight * (end - start)
    return cumul / total_weighted


def build_timeline_from_fixtures(
    min_season: int = 2010,
    max_season: int = 2026,
    snapshot_minutes: list[int] | None = None,
) -> pd.DataFrame:
    """Constrói dataset de snapshots in-play a partir das fixtures históricas.

    Para cada jogo com resultado final, gera um snapshot por minuto em
    `snapshot_minutes`. Cada snapshot contém o estado estimado do jogo
    naquele minuto e os gols restantes observados.

    Returns:
        DataFrame com colunas:
        - match_id, season, home_team, away_team
        - minute, match_minutes
        - home_score_partial, away_score_partial (estimados até o minuto)
        - home_score_final, away_score_final
        - remaining_goals_home, remaining_goals_away
        - home_red_cards, away_red_cards (do agregado)
        - home_corners, away_corners (do agregado)
        - remaining_fraction
    """
    if snapshot_minutes is None:
        snapshot_minutes = SNAPSHOT_MINUTES

    fixtures = load_wc_fixtures(include_fifa=True)
    if fixtures.empty:
        return pd.DataFrame()

    # Filtrar por season e resultados completos
    df = fixtures[
        (fixtures["season"] >= min_season)
        & (fixtures["season"] <= max_season)
        & fixtures["home_score"].notna()
        & fixtures["away_score"].notna()
    ].copy()

    if df.empty:
        return pd.DataFrame()

    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    # Tentar enriquecer com stats Sofascore
    sofascore_stats = _load_sofascore_stats()

    rows: list[dict] = []
    match_minutes = 90

    for _, game in df.iterrows():
        match_id = game["match_id"]
        hs_final = int(game["home_score"])
        as_final = int(game["away_score"])

        # Stats extras do Sofascore (se disponíveis)
        stats = sofascore_stats.get(
            (str(game["home_team"]), str(game["away_team"]), str(game.get("match_date", ""))),
            {},
        )
        home_reds = int(stats.get("home_red_cards", 0))
        away_reds = int(stats.get("away_red_cards", 0))
        home_corners = int(stats.get("home_corners", 0))
        away_corners = int(stats.get("away_corners", 0))

        for minute in snapshot_minutes:
            if minute >= match_minutes:
                continue

            # Fração NHPP até este minuto
            frac = _nhpp_cumulative_fraction(minute, match_minutes)
            remaining_frac = 1.0 - frac

            # Score parcial estimado (arredondamento probabilístico com seed)
            rng = np.random.default_rng(hash(f"{match_id}_{minute}") % (2**31))
            # Distribuir gols proporcionalmente ao NHPP
            hs_partial = _distribute_goals(hs_final, frac, rng)
            as_partial = _distribute_goals(as_final, frac, rng)

            # Gols restantes (observação real)
            remaining_home = hs_final - hs_partial
            remaining_away = as_final - as_partial

            # Red cards: assumir distribuição uniforme ao longo do jogo
            reds_frac = minute / match_minutes
            home_reds_partial = min(
                int(rng.binomial(home_reds, reds_frac)), home_reds
            )
            away_reds_partial = min(
                int(rng.binomial(away_reds, reds_frac)), away_reds
            )

            rows.append({
                "match_id": match_id,
                "season": int(game["season"]),
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "minute": minute,
                "match_minutes": match_minutes,
                "home_score_partial": hs_partial,
                "away_score_partial": as_partial,
                "home_score_final": hs_final,
                "away_score_final": as_final,
                "remaining_goals_home": remaining_home,
                "remaining_goals_away": remaining_away,
                "home_red_cards": home_reds_partial,
                "away_red_cards": away_reds_partial,
                "home_corners": int(home_corners * reds_frac),
                "away_corners": int(away_corners * reds_frac),
                "remaining_fraction": round(remaining_frac, 4),
            })

    timeline_df = pd.DataFrame(rows)
    return timeline_df


def _distribute_goals(total_goals: int, frac: float, rng: np.random.Generator) -> int:
    """Distribui gols usando binomial: cada gol tem prob `frac` de ter sido antes."""
    if total_goals == 0:
        return 0
    return int(rng.binomial(total_goals, frac))


def _load_sofascore_stats() -> dict:
    """Carrega stats Sofascore indexadas por (home_team, away_team, match_date)."""
    stats_path = settings.lake_root / "sofascore" / "match_stats.parquet"
    if not stats_path.exists():
        return {}

    try:
        df = pd.read_parquet(stats_path)
        result = {}
        for _, row in df.iterrows():
            key = (
                str(row.get("home_team", "")),
                str(row.get("away_team", "")),
                str(row.get("match_date", ""))[:10],
            )
            result[key] = {
                "home_red_cards": row.get("home_red_cards", 0) or 0,
                "away_red_cards": row.get("away_red_cards", 0) or 0,
                "home_corners": row.get("home_corners", 0) or 0,
                "away_corners": row.get("away_corners", 0) or 0,
                "home_xg": row.get("home_xg"),
                "away_xg": row.get("away_xg"),
            }
        return result
    except Exception:
        return {}


def save_timeline(timeline_df: pd.DataFrame, path: Path | None = None) -> Path:
    """Persiste timeline em Parquet particionado por season."""
    if path is None:
        path = settings.lake_root / "silver" / "wc_timeline" / "timeline.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    timeline_df.to_parquet(path, index=False)
    return path


def load_timeline(path: Path | None = None) -> pd.DataFrame:
    """Carrega timeline do Parquet."""
    if path is None:
        path = settings.lake_root / "silver" / "wc_timeline" / "timeline.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
