"""Mapeamento de tipos de estatística ScoreAlarm (overview + SSE team stats)."""
from __future__ import annotations

from typing import Any

# Períodos no payload SSE aninhado (0=FT, 1=1T, 2=2T, 6=período corrente).
PERIOD_FT = "0"
PERIOD_CURRENT = "6"

# Tipos no overview.statistics[].data (confirmado em jogos ao vivo).
OVERVIEW_POSSESSION = 1
OVERVIEW_SHOTS = 18
OVERVIEW_SHOTS_ON_GOAL = 2
OVERVIEW_SHOTS_OFF_GOAL = 3
OVERVIEW_FREE_KICKS = 4
OVERVIEW_CORNERS = 5
OVERVIEW_THROW_INS = 7
OVERVIEW_GOAL_KICKS = 9
OVERVIEW_YELLOW_CARDS = 12
OVERVIEW_DANGEROUS_ATTACKS = 13
OVERVIEW_ATTACKS = 14

# Tipos no SSE teams.stats (IDs distintos do overview).
SSE_GOALS = "1"
SSE_SHOTS = "5"
SSE_SHOTS_ON_GOAL = "6"
SSE_SHOTS_OFF_GOAL = "7"
SSE_CORNERS = "11"
SSE_FREE_KICKS = "13"
SSE_THROW_INS = "19"
SSE_YELLOW_CARDS = "24"

OVERVIEW_STAT_LABELS: dict[int, str] = {
    OVERVIEW_POSSESSION: "possession_pct",
    OVERVIEW_SHOTS: "shots",
    OVERVIEW_SHOTS_ON_GOAL: "shots_on_target",
    OVERVIEW_SHOTS_OFF_GOAL: "shots_off_target",
    OVERVIEW_FREE_KICKS: "free_kicks",
    OVERVIEW_CORNERS: "corners",
    OVERVIEW_THROW_INS: "throw_ins",
    OVERVIEW_GOAL_KICKS: "goal_kicks",
    OVERVIEW_YELLOW_CARDS: "yellow_cards",
    OVERVIEW_DANGEROUS_ATTACKS: "dangerous_attacks",
    OVERVIEW_ATTACKS: "attacks",
}

SSE_STAT_LABELS: dict[str, str] = {
    SSE_GOALS: "goals",
    SSE_SHOTS: "shots",
    SSE_SHOTS_ON_GOAL: "shots_on_target",
    SSE_SHOTS_OFF_GOAL: "shots_off_target",
    SSE_CORNERS: "corners",
    SSE_FREE_KICKS: "free_kicks",
    SSE_THROW_INS: "throw_ins",
    SSE_YELLOW_CARDS: "yellow_cards",
}


def _parse_numeric(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace("%", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_overview_statistics(overview: dict[str, Any], *, period: int = 0) -> dict[str, float | None]:
    """Extrai stats home/away do bloco ``statistics`` do overview."""
    out: dict[str, float | None] = {}
    stats_blocks = overview.get("statistics") or []
    block = next(
        (b for b in stats_blocks if int(b.get("period") if b.get("period") is not None else -1) == period),
        None,
    )
    if not block:
        return out
    for row in block.get("data") or []:
        stat_type = row.get("type")
        if stat_type is None:
            continue
        key = OVERVIEW_STAT_LABELS.get(int(stat_type))
        if not key:
            continue
        home_val = _parse_numeric(row.get("team1"))
        away_val = _parse_numeric(row.get("team2"))
        out[f"home_{key}"] = home_val
        out[f"away_{key}"] = away_val
    return out


def _extract_sse_stat(team_stats: dict[str, Any], stat_id: str, period: str = PERIOD_FT) -> int | None:
    node = team_stats.get(stat_id)
    if not isinstance(node, dict):
        return None
    period_node = node.get(period) or node.get(PERIOD_CURRENT)
    if not isinstance(period_node, dict):
        return None
    val = _parse_numeric(period_node.get("val"))
    if val is None:
        return None
    return int(val)


def parse_team_stats_sse(payload: dict[str, Any]) -> dict[str, float | None]:
    """Normaliza payload SSE ``teams.home/away.stats``."""
    teams = payload.get("teams") or {}
    home_stats = (teams.get("home") or {}).get("stats") or {}
    away_stats = (teams.get("away") or {}).get("stats") or {}
    out: dict[str, float | None] = {}
    for stat_id, field in SSE_STAT_LABELS.items():
        home_val = _extract_sse_stat(home_stats, stat_id)
        away_val = _extract_sse_stat(away_stats, stat_id)
        if home_val is not None:
            out[f"home_{field}"] = float(home_val)
        if away_val is not None:
            out[f"away_{field}"] = float(away_val)
    return out


def merge_live_stats(
    overview_stats: dict[str, float | None],
    sse_stats: dict[str, float | None],
) -> dict[str, float | None]:
    """Overview tem prioridade (inclui posse); SSE complementa chaves ausentes."""
    merged = dict(sse_stats)
    merged.update({k: v for k, v in overview_stats.items() if v is not None})
    return merged


__all__ = [
    "merge_live_stats",
    "parse_overview_statistics",
    "parse_team_stats_sse",
]
