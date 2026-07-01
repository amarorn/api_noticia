"""Orquestra overview + team stats SSE + H2H ScoreAlarm."""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from ingest.superbet.scorealarm.client import ScorealarmClient, ScorealarmClientError
from ingest.superbet.scorealarm.players import build_top_players, parse_player_stats_sse
from ingest.superbet.scorealarm.prematch import build_prematch_context
from ingest.superbet.scorealarm.social import fetch_social_top_picks
from ingest.superbet.scorealarm.stat_types import merge_live_stats, parse_overview_statistics, parse_team_stats_sse
from ingest.superbet.scorealarm.store import load_latest_scorealarm_snapshot, save_scorealarm_snapshot
from ingest.superbet.scorealarm.ticker import parse_timeline_events

logger = logging.getLogger(__name__)


def _overview_path() -> str:
    return f"/v2/soccer/fixtures/overview/{settings.scorealarm_brand}/{settings.scorealarm_locale}"


def _team_stats_sse_path() -> str:
    return (
        f"/v2/soccer/fixtures/live/teams/stats/{settings.scorealarm_brand}/"
        f"{settings.scorealarm_locale}"
    )


def _players_stats_sse_path() -> str:
    return (
        f"/v2/soccer/fixtures/live/players/stats/{settings.scorealarm_brand}/"
        f"{settings.scorealarm_locale}"
    )


def _h2h_path() -> str:
    return f"/v2/soccer/fixtures/h2h/{settings.scorealarm_brand}/{settings.scorealarm_locale}"


def fetch_scorealarm_context(
    event_id: int,
    *,
    home_team: str,
    away_team: str,
    use_stale_fallback: bool = True,
) -> dict[str, Any] | None:
    """Busca contexto ao vivo ScoreAlarm; em falha retorna bronze ``latest.json``."""
    if not settings.scorealarm_enabled:
        return None

    client = ScorealarmClient()
    fixture_id = client.offer_fixture_id(event_id)
    context: dict[str, Any] = {
        "event_id": event_id,
        "fixture_id": fixture_id,
        "source": "scorealarm",
        "available": False,
        "stale": False,
        "stats": {},
        "timeline": [],
        "h2h": None,
        "prematch": None,
        "players": [],
        "social": None,
        "scores_id": None,
        "team_ids": {},
    }

    try:
        overview = client.fetch_json(_overview_path(), params={"fixture-id": fixture_id})
        overview_stats = parse_overview_statistics(overview, period=0)
        team1 = overview.get("team1") or {}
        team2 = overview.get("team2") or {}
        context["scores_id"] = overview.get("id")
        context["team_ids"] = {
            "home": team1.get("id"),
            "away": team2.get("id"),
        }
        context["timeline"] = parse_timeline_events(
            overview.get("live_events") or [],
            home_team=home_team or str(team1.get("name") or ""),
            away_team=away_team or str(team2.get("name") or ""),
        )

        sse_payload = client.fetch_first_sse_json(
            _team_stats_sse_path(),
            params={"fixture-id": fixture_id},
        )
        sse_stats = parse_team_stats_sse(sse_payload or {})
        context["stats"] = merge_live_stats(overview_stats, sse_stats)
        context["available"] = bool(context["stats"] or context["timeline"])

        home_name = home_team or str(team1.get("name") or "")
        away_name = away_team or str(team2.get("name") or "")

        try:
            players_sse = client.fetch_first_sse_json(
                _players_stats_sse_path(),
                params={"fixture-id": fixture_id},
            )
            parsed_players = parse_player_stats_sse(
                players_sse,
                home_team=home_name,
                away_team=away_name,
            )
            context["players"] = build_top_players(parsed_players)
            if context["players"]:
                context["available"] = True
        except ScorealarmClientError as exc:
            logger.debug("scorealarm_players_skip event_id=%s: %s", event_id, exc)

        context["social"] = fetch_social_top_picks(fixture_id, event_id=event_id)

        team1_id = context["team_ids"].get("home")
        team2_id = context["team_ids"].get("away")
        if team1_id and team2_id:
            try:
                h2h = client.fetch_json(
                    _h2h_path(),
                    params={"team1-id": team1_id, "team2-id": team2_id},
                )
                stats = h2h.get("h2h_statistics") or {}
                context["h2h"] = {
                    "home_wins": int(stats.get("team1") or 0),
                    "draws": int(stats.get("draw") or 0),
                    "away_wins": int(stats.get("team2") or 0),
                    "since_year": int(h2h.get("h2h_year_since") or 0) or None,
                }
                context["prematch"] = build_prematch_context(
                    overview,
                    h2h,
                    home_team=home_name,
                    away_team=away_name,
                )
            except ScorealarmClientError as exc:
                logger.debug("scorealarm_h2h_skip event_id=%s: %s", event_id, exc)

        save_scorealarm_snapshot(event_id, context)
        return context
    except ScorealarmClientError as exc:
        logger.warning("scorealarm_fetch_falha event_id=%s: %s", event_id, exc)
        if not use_stale_fallback:
            return None
        stale = load_latest_scorealarm_snapshot(event_id)
        if stale is None:
            return None
        stale = dict(stale)
        stale["stale"] = True
        stale["available"] = bool(stale.get("stats") or stale.get("timeline"))
        return stale


def scorealarm_to_live_stats(context: dict[str, Any] | None) -> dict[str, float | None]:
    """Mapeia stats ScoreAlarm para chaves usadas em ``live_stats_payload``."""
    if not context or not context.get("available"):
        return {}
    stats = context.get("stats") or {}
    out: dict[str, float | None] = {}
    if stats.get("home_possession_pct") is not None:
        out["home_possession_pct"] = stats["home_possession_pct"]
        out["away_possession_pct"] = stats.get("away_possession_pct")
    if stats.get("home_shots_on_target") is not None:
        out["home_shots_on_target"] = stats["home_shots_on_target"]
        out["away_shots_on_target"] = stats.get("away_shots_on_target")
    return out


__all__ = ["fetch_scorealarm_context", "scorealarm_to_live_stats"]
