"""Análise dos últimos 10 jogos por perna do bilhete combo KXL."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import structlog

from ingest.sofascore.incidents_ht import map_half_time_metrics
from ingest.sofascore.stats_dataset import load_match_stats_history
from models.wc_team_patterns import get_team_patterns
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()

WINDOW_SIZE = 10


def _leg_metric_value(leg: dict[str, Any], ht: dict[str, int | float | str | bool]) -> float | None:
    stat = leg.get("stat")
    period = leg.get("period")
    entity = leg.get("entity", "match_total")

    if period == "first_half":
        if not ht.get("ht_available"):
            return None
        if stat == "goals":
            if entity == "match_total":
                return float(ht["ht_goals_home"] + ht["ht_goals_away"])
            return None
        if stat == "yellow_cards":
            if entity == "match_total":
                return float(ht["ht_yellow_cards_home"] + ht["ht_yellow_cards_away"])
            return None
    elif period == "full_time":
        if stat == "goals" and entity == "match_total":
            return float(ht.get("ft_goals_home", 0) + ht.get("ft_goals_away", 0))
        if stat == "yellow_cards" and entity == "match_total":
            return float(ht.get("ft_yellow_home", 0) + ht.get("ft_yellow_away", 0))
    return None


def _leg_hit(leg: dict[str, Any], value: float | None) -> bool | None:
    if value is None:
        return None
    line = leg.get("line")
    direction = leg.get("direction")
    if line is None or direction not in {"over", "under"}:
        return None
    if direction == "under":
        return value < float(line)
    return value > float(line)


def _find_kxl_pattern(team_en: str, leg: dict[str, Any]) -> dict[str, Any] | None:
    block = get_team_patterns(team_en)
    if not block:
        return None
    for patterns in block.get("axes", {}).values():
        for p in patterns:
            if (
                p.get("stat") == leg.get("stat")
                and p.get("period") == leg.get("period")
                and p.get("direction") == leg.get("direction")
                and p.get("entity") == leg.get("entity", "match_total")
            ):
                return {
                    "team": normalize_national_team(team_en),
                    "hits": p.get("hits"),
                    "total": p.get("total"),
                    "hit_rate": p.get("hit_rate"),
                    "line": p.get("line"),
                    "source": "kxl_patterns",
                }
    return None


def _team_last_matches(team: str, *, window: int = WINDOW_SIZE) -> pd.DataFrame:
    canonical = normalize_national_team(team)
    df = load_match_stats_history()
    if df.empty:
        return df
    mask = (df["home_team"] == canonical) | (df["away_team"] == canonical)
    sub = df.loc[mask].copy()
    if sub.empty:
        return sub
    sub = sub.sort_values("match_date", ascending=False).head(window)
    return sub.reset_index(drop=True)


def _fetch_ht_metrics(
    event_id: int,
    row: pd.Series,
    *,
    client: Any | None = None,
    cache: dict[int, dict[str, int | float]] | None = None,
) -> dict[str, int | float]:
    if cache is not None and event_id in cache:
        return cache[event_id]

    ht: dict[str, int | float | str] = {
        "ht_goals_home": 0,
        "ht_goals_away": 0,
        "ht_yellow_cards_home": 0,
        "ht_yellow_cards_away": 0,
        "ft_goals_home": float(row.get("incident_goals_home") or 0),
        "ft_goals_away": float(row.get("incident_goals_away") or 0),
        "ft_yellow_home": float(row.get("incident_yellow_cards_home") or row.get("home_yellow_cards") or 0),
        "ft_yellow_away": float(row.get("incident_yellow_cards_away") or row.get("away_yellow_cards") or 0),
        "incidents_source": "unavailable",
        "ht_available": False,
    }

    if client is not None:
        try:
            payload = client.event_incidents(int(event_id))
            ht.update(map_half_time_metrics(payload))
            ht["incidents_source"] = "sofascore_api"
            ht["ht_available"] = True
        except Exception as exc:
            logger.warning("combo_last10_incidents_failed", event_id=event_id, error=str(exc))

    if cache is not None:
        cache[event_id] = ht
    return ht


def _format_match_date(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y-%m-%d")


def _metric_detail(leg: dict[str, Any], value: float | None, *, ht_available: bool) -> str:
    if value is None:
        if leg.get("period") == "first_half" and not ht_available:
            return "1T indisponível (sem incidentes)"
        return "métrica indisponível"
    stat = leg.get("stat")
    period = leg.get("period")
    if stat == "goals" and period == "first_half":
        return f"{value:.0f} gol(s) no 1T"
    if stat == "yellow_cards" and period == "first_half":
        return f"{value:.0f} cartão(ões) amarelo(s) no 1T"
    if stat == "goals":
        return f"{value:.0f} gol(s) na partida"
    if stat == "yellow_cards":
        return f"{value:.0f} cartão(ões) amarelo(s) na partida"
    return f"valor {value:.1f}"


def _analyze_team_leg(
    team: str,
    team_en: str,
    leg: dict[str, Any],
    *,
    client: Any | None = None,
    cache: dict[int, dict[str, int | float]] | None = None,
    window: int = WINDOW_SIZE,
) -> dict[str, Any]:
    matches_df = _team_last_matches(team, window=window)
    kxl = _find_kxl_pattern(team_en, leg)
    rows: list[dict[str, Any]] = []
    hits = 0
    evaluated = 0

    for _, match in matches_df.iterrows():
        event_id = int(match["event_id"])
        ht = _fetch_ht_metrics(event_id, match, client=client, cache=cache)
        value = _leg_metric_value(leg, ht)
        hit = _leg_hit(leg, value)
        if hit is not None:
            evaluated += 1
            if hit:
                hits += 1
        rows.append(
            {
                "event_id": event_id,
                "match_date": _format_match_date(match.get("match_date")),
                "home_team": str(match.get("home_team") or ""),
                "away_team": str(match.get("away_team") or ""),
                "metric_value": value,
                "hit": hit,
                "detail": _metric_detail(leg, value, ht_available=bool(ht.get("ht_available"))),
                "incidents_source": ht.get("incidents_source"),
            }
        )

    total = len(rows) or window
    return {
        "team": normalize_national_team(team),
        "hits": hits,
        "total": total,
        "evaluated": evaluated,
        "hit_rate": round(hits / evaluated, 3) if evaluated else None,
        "kxl_pattern": kxl,
        "matches": rows,
    }


def build_last10_analysis(
    home_team: str,
    away_team: str,
    legs: list[dict[str, Any]],
    *,
    client: Any | None = None,
    window: int = WINDOW_SIZE,
) -> dict[str, Any]:
    """Fundamenta cada perna do bilhete com os últimos N jogos de cada seleção."""
    from models.wc_team_patterns import _canonical_team

    home_en = _canonical_team(home_team)
    away_en = _canonical_team(away_team)
    cache: dict[int, dict[str, int | float]] = {}
    leg_reports: list[dict[str, Any]] = []

    for leg in legs:
        team_reports = [
            _analyze_team_leg(
                home_team,
                home_en,
                leg,
                client=client,
                cache=cache,
                window=window,
            ),
            _analyze_team_leg(
                away_team,
                away_en,
                leg,
                client=client,
                cache=cache,
                window=window,
            ),
        ]
        crossing_hits = min(r["hits"] for r in team_reports) if team_reports else 0
        evaluated_min = min(r["evaluated"] for r in team_reports) if team_reports else 0
        crossing_total = leg.get("total") or window
        leg_reports.append(
            {
                "rank": leg.get("rank"),
                "label": leg.get("label"),
                "stat": leg.get("stat"),
                "period": leg.get("period"),
                "direction": leg.get("direction"),
                "line": leg.get("line"),
                "pattern_ref": leg.get("pattern_ref"),
                "kxl_crossing": {
                    "hits": leg.get("hits"),
                    "total": leg.get("total"),
                    "hit_rate": leg.get("hit_rate"),
                },
                "sofascore_crossing": {
                    "hits": crossing_hits if evaluated_min > 0 else None,
                    "total": window if evaluated_min > 0 else None,
                    "hit_rate": round(crossing_hits / evaluated_min, 3)
                    if evaluated_min > 0
                    else None,
                    "evaluated": evaluated_min,
                },
                "teams": team_reports,
            }
        )

    incidents_fetched = sum(
        1
        for metrics in cache.values()
        if metrics.get("incidents_source") == "sofascore_api"
    )

    return {
        "window_size": window,
        "source_note": (
            "KXL: últimas 10 partidas oficiais de Copa por seleção (padrões 9/10–10/10). "
            "Sofascore: últimos jogos no lake local; 1T via incidentes quando disponível."
        ),
        "incidents_fetched": incidents_fetched,
        "legs": leg_reports,
    }
