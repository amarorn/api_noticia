"""Parser de estatísticas por jogador (SSE ScoreAlarm)."""
from __future__ import annotations

from typing import Any

from ingest.superbet.scorealarm.stat_types import PERIOD_CURRENT, _parse_numeric

# IDs observados no SSE ``live/players/stats`` (período 6 = corrente).
PLAYER_STAT_LABELS: dict[str, str] = {
    "1": "goals",
    "2": "assists",
    "5": "shots",
    "6": "shots_on_target",
    "11": "corners",
    "17": "fouls_committed",
    "18": "fouls_suffered",
    "24": "yellow_cards",
    "26": "passes",
    "32": "saves",
}

POSITION_LABELS: dict[int, str] = {
    1: "GOL",
    2: "DEF",
    3: "MEI",
    4: "ATA",
}


def _extract_player_stat(stats: dict[str, Any], stat_id: str) -> int | None:
    node = stats.get(stat_id)
    if not isinstance(node, dict):
        return None
    period_node = node.get(PERIOD_CURRENT) or node.get("0")
    if not isinstance(period_node, dict):
        return None
    val = _parse_numeric(period_node.get("val"))
    if val is None:
        return None
    return int(val)


def _player_display_name(meta: dict[str, Any]) -> str:
    for preferred_type in (2, 1, 3):
        for item in meta.get("names") or []:
            if int(item.get("type") or 0) == preferred_type:
                name = str(item.get("name") or "").strip()
                if name:
                    return name
    return str(meta.get("scores_id") or "Jogador")


def _player_team_label(meta: dict[str, Any], *, home_team: str, away_team: str) -> str:
    side = int(meta.get("team_side") or 0)
    if side == 1:
        return home_team
    if side == 2:
        return away_team
    for item in meta.get("team_names") or []:
        if int(item.get("type") or 0) == 1:
            return str(item.get("name") or "")
    return ""


def parse_player_stats_sse(
    payload: dict[str, Any] | None,
    *,
    home_team: str = "",
    away_team: str = "",
) -> list[dict[str, Any]]:
    """Normaliza mapa ``player_id -> stats`` do SSE de jogadores."""
    if not payload:
        return []

    players: list[dict[str, Any]] = []
    for _player_id, row in payload.items():
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") or {}
        stats_raw = row.get("stats") or {}
        stats: dict[str, int] = {}
        for stat_id, field in PLAYER_STAT_LABELS.items():
            value = _extract_player_stat(stats_raw, stat_id)
            if value is not None and value > 0:
                stats[field] = value

        position = int(meta.get("position") or 0)
        players.append(
            {
                "name": _player_display_name(meta),
                "team": _player_team_label(meta, home_team=home_team, away_team=away_team),
                "side": int(meta.get("team_side") or 0),
                "jersey": str(meta.get("jersey_number") or ""),
                "position": position,
                "position_label": POSITION_LABELS.get(position, ""),
                "stats": stats,
            }
        )
    return players


def _activity_score(stats: dict[str, int]) -> float:
    return (
        stats.get("goals", 0) * 5
        + stats.get("assists", 0) * 3
        + stats.get("shots_on_target", 0) * 2
        + stats.get("shots", 0)
        + stats.get("saves", 0) * 2
    )


def build_top_players(players: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    """Ranqueia jogadores com maior atividade ofensiva/relevância ao vivo."""
    ranked = sorted(
        players,
        key=lambda p: (_activity_score(p.get("stats") or {}), p.get("stats", {}).get("goals", 0)),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for player in ranked:
        stats = player.get("stats") or {}
        if _activity_score(stats) <= 0:
            continue
        out.append(
            {
                "name": player.get("name"),
                "team": player.get("team"),
                "side": player.get("side"),
                "jersey": player.get("jersey"),
                "position_label": player.get("position_label"),
                "stats": stats,
                "highlights": _player_highlights(stats),
            }
        )
        if len(out) >= limit:
            break
    return out


def _player_highlights(stats: dict[str, int]) -> list[str]:
    labels: list[str] = []
    if stats.get("goals"):
        labels.append(f"{stats['goals']} gol(s)")
    if stats.get("assists"):
        labels.append(f"{stats['assists']} assist.")
    if stats.get("shots_on_target"):
        labels.append(f"{stats['shots_on_target']} no gol")
    elif stats.get("shots"):
        labels.append(f"{stats['shots']} final.")
    if stats.get("saves"):
        labels.append(f"{stats['saves']} defesa(s)")
    if stats.get("yellow_cards"):
        labels.append(f"{stats['yellow_cards']} amarelo")
    return labels


__all__ = [
    "build_top_players",
    "parse_player_stats_sse",
]
