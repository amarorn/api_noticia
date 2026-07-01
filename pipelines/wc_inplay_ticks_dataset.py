"""Dataset de snapshots in-play a partir de live_ticks.parquet (poll real)."""
from __future__ import annotations

import pandas as pd

from ingest.superbet.live_ticks import live_ticks_path
from pipelines.inplay_event_finals import load_all_event_final_scores


def build_timeline_from_live_ticks(
    *,
    min_minute: int = 1,
    max_minute: int = 89,
    match_minutes: int = 90,
) -> pd.DataFrame:
    """Converte ticks reais em timeline compatível com fit_momentum_mle.

    Cada linha = um snapshot (evento, minuto) com gols parciais observados
    e gols restantes derivados do placar final bronze.
    """
    path = live_ticks_path()
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(path)
    if df.empty or "event_id" not in df.columns:
        return pd.DataFrame()

    finals = load_all_event_final_scores()
    if not finals:
        return pd.DataFrame()

    work = df[df["event_id"].notna()].copy()
    work["event_id"] = work["event_id"].astype(int)
    work = work[work["event_id"].isin(finals.keys())]
    if work.empty:
        return pd.DataFrame()

    for col in ("minute", "home_score", "away_score"):
        if col not in work.columns:
            return pd.DataFrame()
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["minute", "home_score", "away_score"])
    work["minute"] = work["minute"].astype(int)
    work = work[(work["minute"] >= min_minute) & (work["minute"] <= max_minute)]
    if work.empty:
        return pd.DataFrame()

    if "captured_at" in work.columns:
        work = work.sort_values("captured_at")
    work = work.drop_duplicates(subset=["event_id", "minute"], keep="last")

    rows: list[dict] = []
    for _, tick in work.iterrows():
        eid = int(tick["event_id"])
        final = finals[eid]
        hs_final = int(final["home_score_final"])
        as_final = int(final["away_score_final"])
        minute = int(tick["minute"])
        hs_partial = int(tick["home_score"])
        as_partial = int(tick["away_score"])

        if hs_partial > hs_final or as_partial > as_final:
            continue

        remaining_home = hs_final - hs_partial
        remaining_away = as_final - as_partial
        remaining_frac = max(0.0, (match_minutes - minute) / match_minutes)

        rows.append(
            {
                "match_id": f"live_{eid}",
                "season": 2026,
                "home_team": tick.get("home_team") or final.get("home_team"),
                "away_team": tick.get("away_team") or final.get("away_team"),
                "minute": minute,
                "match_minutes": match_minutes,
                "home_score_partial": hs_partial,
                "away_score_partial": as_partial,
                "home_score_final": hs_final,
                "away_score_final": as_final,
                "remaining_goals_home": remaining_home,
                "remaining_goals_away": remaining_away,
                "home_red_cards": int(tick.get("home_red_cards") or 0),
                "away_red_cards": int(tick.get("away_red_cards") or 0),
                "home_corners": int(tick.get("home_corners") or 0),
                "away_corners": int(tick.get("away_corners") or 0),
                "remaining_fraction": remaining_frac,
                "source": "live_ticks",
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


__all__ = ["build_timeline_from_live_ticks"]
