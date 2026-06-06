from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ingest.sofascore.stats_dataset import STAT_COLUMNS, load_match_stats_history

SOFASCORE_FEATURE_NAMES = [
    "sofa_xg_for_diff_last5",
    "sofa_xg_against_diff_last5",
    "sofa_possession_diff_last5",
    "sofa_shots_on_target_diff_last5",
    "sofa_big_chances_diff_last5",
    "sofa_stats_available",
]

ROLLING_WINDOW = 5
MIN_TEAM_MATCHES = 2


@dataclass(frozen=True)
class TeamRollingStats:
    xg_for: float
    xg_against: float
    possession: float
    shots_on_target: float
    big_chances: float
    samples: int


def _team_perspective_rows(df: pd.DataFrame, team: str) -> pd.DataFrame:
    if df.empty:
        return df

    home = df[df["home_team"] == team].copy()
    away = df[df["away_team"] == team].copy()

    home["xg_for"] = home["home_xg"]
    home["xg_against"] = home["away_xg"]
    home["possession"] = home["home_possession_pct"]
    home["shots_on_target"] = home["home_shots_on_target"]
    home["big_chances"] = home["home_big_chances"]

    away["xg_for"] = away["away_xg"]
    away["xg_against"] = away["home_xg"]
    away["possession"] = away["away_possession_pct"]
    away["shots_on_target"] = away["away_shots_on_target"]
    away["big_chances"] = away["away_big_chances"]

    cols = ["match_date", "xg_for", "xg_against", "possession", "shots_on_target", "big_chances"]
    combined = pd.concat([home[cols], away[cols]], ignore_index=True)
    return combined.sort_values("match_date")


def team_rolling_stats(
    df: pd.DataFrame,
    team: str,
    *,
    window: int = ROLLING_WINDOW,
) -> TeamRollingStats | None:
    rows = _team_perspective_rows(df, team)
    if rows.empty:
        return None

    usable = rows.dropna(subset=["xg_for", "xg_against"])
    if len(usable) < MIN_TEAM_MATCHES:
        return None

    tail = usable.tail(window)

    def _mean(col: str) -> float:
        series = pd.to_numeric(tail[col], errors="coerce").dropna()
        return float(series.mean()) if not series.empty else 0.0

    return TeamRollingStats(
        xg_for=_mean("xg_for"),
        xg_against=_mean("xg_against"),
        possession=_mean("possession"),
        shots_on_target=_mean("shots_on_target"),
        big_chances=_mean("big_chances"),
        samples=len(tail),
    )


def _rolling_to_dict(stats: TeamRollingStats) -> dict[str, float | int]:
    return {
        "xg_for": round(stats.xg_for, 2),
        "xg_against": round(stats.xg_against, 2),
        "possession_pct": round(stats.possession, 1),
        "shots_on_target": round(stats.shots_on_target, 1),
        "big_chances": round(stats.big_chances, 1),
        "samples": stats.samples,
    }


def build_gold_wc_match_features_df(*, stats_df: pd.DataFrame | None = None) -> pd.DataFrame:
    history = stats_df if stats_df is not None else load_match_stats_history()
    if history.empty:
        return pd.DataFrame(
            columns=[
                "event_id",
                "home_team",
                "away_team",
                "match_date",
                *SOFASCORE_FEATURE_NAMES,
                "built_at",
            ]
        )

    ordered = history.sort_values("match_date").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    built_at = datetime.now(timezone.utc).isoformat()

    for _, match in ordered.iterrows():
        match_date = match.get("match_date")
        if pd.isna(match_date):
            continue
        before = pd.to_datetime(match_date, utc=True).to_pydatetime()
        vec = sofascore_feature_vector(
            str(match["home_team"]),
            str(match["away_team"]),
            before_date=before,
            stats_df=history,
        )
        rows.append(
            {
                "event_id": int(match["event_id"]),
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "match_date": before,
                **dict(zip(SOFASCORE_FEATURE_NAMES, vec, strict=True)),
                "built_at": built_at,
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["match_date"] = pd.to_datetime(out["match_date"], utc=True, errors="coerce")
    return out


def sofascore_feature_vector(
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    stats_df: pd.DataFrame | None = None,
) -> list[float]:
    df = stats_df if stats_df is not None else load_match_stats_history(before_date=before_date)
    home = team_rolling_stats(df, home_team)
    away = team_rolling_stats(df, away_team)

    if home is None or away is None:
        return [0.0] * (len(SOFASCORE_FEATURE_NAMES) - 1) + [0.0]

    return [
        home.xg_for - away.xg_for,
        home.xg_against - away.xg_against,
        home.possession - away.possession,
        home.shots_on_target - away.shots_on_target,
        home.big_chances - away.big_chances,
        1.0,
    ]


def sofascore_breakdown(
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    stats_df: pd.DataFrame | None = None,
) -> dict:
    df = stats_df if stats_df is not None else load_match_stats_history(before_date=before_date)
    home = team_rolling_stats(df, home_team)
    away = team_rolling_stats(df, away_team)
    vec = sofascore_feature_vector(
        home_team, away_team, before_date=before_date, stats_df=df
    )
    features = dict(zip(SOFASCORE_FEATURE_NAMES, vec, strict=True))
    return {
        "available": features["sofa_stats_available"] == 1.0,
        "window": ROLLING_WINDOW,
        "min_team_matches": MIN_TEAM_MATCHES,
        "features": {k: round(v, 3) for k, v in features.items()},
        "home_last5": _rolling_to_dict(home) if home else None,
        "away_last5": _rolling_to_dict(away) if away else None,
        "parquet_matches_before": len(df),
    }


def format_sofascore_context(
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
) -> str | None:
    info = sofascore_breakdown(home_team, away_team, before_date=before_date)
    if not info["available"]:
        return (
            "## Sofascore (últimos 5 jogos)\n"
            "- Dados indisponíveis no histórico parquet antes desta data "
            f"({info['parquet_matches_before']} jogos no recorte)."
        )

    h = info["home_last5"]
    a = info["away_last5"]
    f = info["features"]
    lines = [
        "## Sofascore (média últimos 5 jogos)",
        "",
        f"### {home_team}",
        f"- xG a favor: {h['xg_for']} | xG contra: {h['xg_against']} | posse: {h['possession_pct']}%",
        f"- Chutes no gol: {h['shots_on_target']} | grandes chances: {h['big_chances']} (n={h['samples']})",
        "",
        f"### {away_team}",
        f"- xG a favor: {a['xg_for']} | xG contra: {a['xg_against']} | posse: {a['possession_pct']}%",
        f"- Chutes no gol: {a['shots_on_target']} | grandes chances: {a['big_chances']} (n={a['samples']})",
        "",
        "### Diferenciais (mandante − visitante)",
        f"- Δ xG a favor: {f['sofa_xg_for_diff_last5']:+.2f}",
        f"- Δ xG contra: {f['sofa_xg_against_diff_last5']:+.2f}",
        f"- Δ posse: {f['sofa_possession_diff_last5']:+.1f} pp",
        f"- Δ chutes no gol: {f['sofa_shots_on_target_diff_last5']:+.1f}",
        f"- Δ grandes chances: {f['sofa_big_chances_diff_last5']:+.1f}",
    ]
    return "\n".join(lines)


def apply_sofascore_nudge(
    probs: dict[str, float],
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    scale: float = 0.06,
) -> tuple[dict[str, float], dict | None]:
    """Desloca levemente 1/X/2 quando há rolling Sofascore (sinal de xG + posse)."""
    info = sofascore_breakdown(home_team, away_team, before_date=before_date)
    if not info["available"]:
        return probs, None

    feats = info["features"]
    xg_diff = float(feats["sofa_xg_for_diff_last5"])
    poss_diff = float(feats["sofa_possession_diff_last5"]) / 100.0
    signal = 0.75 * xg_diff + 0.25 * poss_diff
    delta = scale * max(-1.0, min(1.0, signal / 2.0))

    p1 = probs["1"] + delta
    p2 = probs["2"] - delta
    px = probs["X"]
    total = max(p1 + px + p2, 1e-9)
    adjusted = {"1": p1 / total, "X": px / total, "2": p2 / total}
    meta = {
        "delta_home": round(delta, 4),
        "signal": round(signal, 3),
        "scale": scale,
    }
    return adjusted, meta
